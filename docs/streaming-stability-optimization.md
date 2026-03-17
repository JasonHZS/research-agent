# 海外部署流式响应稳定性优化记录

## 问题描述

项目部署到海外服务器后，不管是普通聊天模式还是 Deep Research 模式，AI 的回答都经常卡住甚至直接断联，相比本地部署稳定性差了很多。

### 症状

- 流式输出中途停顿或完全断开
- Deep Research 模式尤其严重，经常长时间无响应后断连
- 本地开发环境无此问题

### 请求链路

```
浏览器 → Cloudflare → Caddy → Next.js rewrite → Python FastAPI
```

生产环境经过多层代理，任一层缓冲或空闲超时都可能导致流式连接断连。

---

## 排查与优化过程

### 第一步：确认前端是否直连 API（已完成）

**问题**：生产环境请求可能仍走 Next.js rewrite 代理，多一层转发增加断连风险。

**验证**：
- `web-ui/.env.local` 已配置 `NEXT_PUBLIC_API_URL=https://api.example.com`
- `web-ui/lib/utils.ts` 的 `getApiBaseUrl()` 在生产环境优先使用该变量
- 浏览器 DevTools 确认请求直接发往 `api.example.com`

**结论**：前端已直连 API 子域名，绕过了 Next.js rewrite。

### 第二步：Cloudflare 配置（已完成）

**问题**：Cloudflare 免费版会缓冲 SSE 响应，导致流式输出延迟或断连。

**措施**：
- API 子域名 `api.example.com` 设为灰云（DNS only），不经过 Cloudflare 代理
- 前端域名可保持橙云享受 CDN
- SSL 模式设为「完全 (Full)」，避免 Caddy HTTPS 与 Cloudflare Flexible 冲突导致重定向循环

### 第三步：Caddy 反向代理零缓冲（已完成）

**问题**：早期流接口实际使用的是 NDJSON（`application/x-ndjson`），而不是标准 SSE；这会导致代理层和调试工具都更难以把它当成真正的事件流处理。Caddy 默认也可能对非 `text/event-stream` 响应进行缓冲。

**措施**：

1. 升级 Caddy 从 2.6.2 到 2.11.2（旧版不支持 `flush_interval`）：

```bash
# 添加官方 APT 源
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

2. 配置 `flush_interval -1` 实现逐字节转发：

```
# /etc/caddy/Caddyfile
example.com {
    reverse_proxy localhost:3000
}

api.example.com {
    reverse_proxy localhost:8111 {
        flush_interval -1
    }
}
```

3. 验证并重启：

```bash
caddy validate --config /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

### 第四步：Deep Research 心跳与进度事件（已完成）

**问题**：后端在 Deep Research 模式下，只有 `final_report` 节点的 token 才会发给前端，其他所有中间节点（clarify/analyze/discover/researcher 等）的输出全部被过滤。图可能运行 2-5 分钟，期间没有任何业务数据包发出，代理层会认为连接空闲而回收。

**根因分析**：
- `agent_service.py` 的 `stream_response()` 中，Deep Research 模式用白名单 `{"final_report"}` 过滤节点
- 不在白名单中的节点直接 `continue`，不产生任何输出
- 长时间无数据 → Caddy/ISP/浏览器判定连接死亡 → 断连

**第一次修复的问题**：
- 最初只在“节点切换”时发送一次 `progress`
- 这不是真正 keepalive，因为如果单个节点内部执行很久但没有任何上游 chunk，服务端循环根本不会运行，连接仍然会静默超时

**最终解决方案**：
- 应用层：Deep Research 在长时间无上游 chunk 时，每 15 秒主动发送一次 `progress` 心跳
- 传输层：路由层改成标准 SSE，并额外每 10 秒发送一次 SSE comment heartbeat `:\n\n`
- 前端：`progress` 始终显示，不再因为已有文本内容而隐藏

这样即使研究阶段内部完全无 token，也会持续有字节流出，连接和 UI 都能感知任务还活着。

**改动文件**：

| 文件 | 改动 |
|------|------|
| `src/api/schemas/chat.py` | 新增 `PROGRESS = "progress"` 事件类型 |
| `src/api/services/agent_service.py` | Deep Research 主循环改为带超时的 `anext()` 轮询；节点切换时发 `progress`，空闲超时时也发 `progress` |
| `src/api/routes/chat.py` | 将流协议从 NDJSON 改成标准 SSE（`text/event-stream`），新增 `event:` / `data:` framing，并加入 SSE comment heartbeat |
| `web-ui/lib/types.ts` | StreamEventType 加 `'progress'` |
| `web-ui/lib/stream.ts` | 前端解析器从 NDJSON 改成标准 SSE parser，忽略 comment heartbeat，继续使用 `fetch + POST` |
| `web-ui/hooks/useWebSocket.ts` | 桥接 progress 事件 |
| `web-ui/hooks/useChat.ts` | 加 `progressNode` 状态 |
| `web-ui/components/chat/ChatContainer.tsx` | 处理 progress 事件 |
| `web-ui/components/chat/MessageBubble.tsx` | 显示中文进度标签（如"正在搜索资料..."），并为兜底心跳增加 `working -> 正在处理中...` |
| `web-ui/components/chat/MessageList.tsx` | 传递 progressNode 给 StreamingMessageBubble |

### 第五步：将伪 SSE 重构为真正 SSE（已完成）

**问题**：虽然前端和代码注释一直把该接口称为 “SSE”，但实现上其实是：

- 响应类型：`application/x-ndjson`
- 服务端输出：每行一个 JSON
- 前端解析：按换行拆包后 `JSON.parse`

这只是“HTTP 流式 NDJSON”，不是标准 SSE。因此：

- 不能使用最通用的 SSE comment heartbeat `:\n\n`
- 代理层对 `text/event-stream` 的优化能力用不上
- DevTools / curl / 排障时的观察口径和真正 SSE 不一致

**最终改造**：

- 服务端统一改为标准 SSE frame：

```text
event: progress
data: {"node":"researcher_tools"}

: keepalive

event: message_complete
data: {"is_clarification":false}

```

- 路由层 `Content-Type` 改为 `text/event-stream`
- 保留 `fetch + POST`，不切换到浏览器原生 `EventSource`

**为什么没有切换到 `EventSource`**：

- 当前接口需要 `POST`
- 当前接口需要请求体（`session_id`、`message`、模型参数等）
- 当前接口需要 `Authorization` header

浏览器原生 `EventSource` 只能发 GET，且不适合带自定义认证头。因此这里采用的是：

- 协议层：真正 SSE
- 客户端传输方式：`fetch + ReadableStream`
- 客户端解析方式：手写 SSE parser

### 第六步：定位前后端协议不匹配（已完成）

**现象**：后端日志已经打印出 `ClarifyWithUser` 的问题，但前端长时间停在 `Generating response...`，没有显示澄清问题。

**根因**：后端已经切到标准 SSE，但前端页面仍运行旧版 NDJSON bundle。此时浏览器收到的是：

```text
event: clarification
data: {"question":"..."}

```

但旧前端还在按“每行一个 JSON”解析，于是：

- `event: clarification` 不是合法 JSON
- `data: {...}` 也不是合法 JSON
- 结果是 `clarification` 事件完全没有进入状态层
- `streamingMessage.content` 一直为空，于是 UI 只显示 `Generating response...`

**修复动作**：

- 重新 build / 重启前端服务
- 浏览器 hard refresh，清除旧 JS bundle 缓存

**结论**：这不是 Deep Research graph 本身的问题，也不是 `clarification_status` 丢失；而是协议升级后前后端版本不一致导致的解析失败。

### 第七步：验证方式（已完成）

**后端验证**：

- `tests/test_agent_service_keepalive.py`
  - 验证 Deep Research 在上游静默期间仍会先发 `progress`
- `tests/test_chat_sse.py`
  - 验证 SSE `event:` / `data:` framing 以及 comment frame `:\n\n`

命令：

```bash
uv run pytest tests/test_agent_service_keepalive.py tests/test_chat_sse.py -q
```

**前端验证**：

- TypeScript 编译通过：

```bash
cd web-ui
npm exec tsc --noEmit
```

- 浏览器 Network 中 `/api/chat/stream` 响应应能看到：
  - `text/event-stream`
  - `event: ...`
  - `data: ...`
  - 空行分隔 frame
  - `:\n\n` comment heartbeat

- Deep Research 触发澄清时，前端应显示 Clarify 问题，而不是长时间停留在 `Generating response...`

**节点标签映射**：

| 节点名 | 显示文字 |
|--------|---------|
| clarify | 正在理解问题... |
| analyze | 正在分析需求... |
| plan_sections | 正在规划研究大纲... |
| discover / discover_tools | 正在搜索资料... |
| researcher / researcher_tools | 正在深入研究... |
| extract_output | 正在提取内容... |
| compress_output | 正在整理内容... |
| aggregate | 正在汇总结果... |
| review | 正在审阅报告... |
| final_report | 正在撰写报告... |

---

## 当前状态

| 优化项 | 状态 |
|--------|------|
| 前端直连 API 子域名 | ✅ 已完成 |
| Cloudflare API 灰云 | ✅ 已完成 |
| Caddy flush_interval -1 | ✅ 已完成 |
| Deep Research 应用层 keepalive / progress | ✅ 已完成 |
| 流协议重构为标准 SSE | ✅ 已完成 |
| 路由层 SSE comment heartbeat | ✅ 已完成 |
| 前后端协议不匹配排查 | ✅ 已完成 |

---

## 后续可选优化

- [ ] 为前端 parser 增加独立单元测试（当前已完成 TypeScript 编译校验）
- [ ] 普通模式下如果 LLM 推理时间过长（>30s），评估是否也补充更明确的应用层进度提示
- [ ] 前端断连自动重试机制
- [ ] 监控 SSE 连接存活时长，收集断连统计数据
