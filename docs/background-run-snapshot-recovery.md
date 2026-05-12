# 后台执行与内存快照恢复实现说明

## 背景

本次改造的目标不是做“精确的流式断点续传”，而是解决下面这个更实际的问题：

- 服务进程正常运行
- 一次 chat / Deep Research 任务已经在执行
- 前端 SSE 连接中途断开
- 用户重新连接后，仍然能看到当前已生成的结果，并继续接收后续更新

本次明确 **不引入数据库**，也 **不把 LangGraph saver 从内存版切到持久化版**。因此方案是：

- 后端将任务执行从单次 SSE 请求中解耦，改为后台任务
- 后端在内存中维护当前运行的快照
- 用户重连时，先返回快照，再继续订阅同一个后台任务
- 快照内容在运行时聚合，同时结合 `agent.get_state(thread_id)` 从 LangGraph checkpoint 补齐

---

## 核心思路

### 1. 任务执行与 SSE 连接解耦

旧模型是：

- `POST /api/chat/stream`
- 在这个 HTTP 请求里直接执行 graph
- SSE 连接断开时，这次执行通常也会跟着结束

新模型是：

- `POST /api/chat/stream`
- 只负责启动一个后台 run
- HTTP 连接只负责“订阅这个 run 的事件”
- SSE 连接断开后，后台 run 继续执行

这样，连接生命周期不再等于任务生命周期。

### 2. 为每个会话维护一个后台运行对象

后端新增了两个运行时数据结构：

- `StreamingSnapshot`
  - 保存当前已生成的 assistant 内容、thinking、tool calls、segments、progress node、是否为 clarification、错误状态等
- `BackgroundRun`
  - 保存会话 ID、请求 ID、后台 task、本次运行的 snapshot、当前订阅者集合、terminal event

这些对象只存在于当前 Python 进程内存中。

### 3. 重连时先发快照，再发增量事件

新增订阅逻辑后，用户重连时不是从空白 UI 重新开始，而是：

1. 后端先发一个 `snapshot` 事件
2. 前端用这个 snapshot 直接恢复当前 `streamingMessage`
3. 如果后台 run 仍在执行，则继续接收新的 `token` / `progress` / `tool_call_*` / `message_complete`

这实现的是“状态恢复”，不是“事件级重放”。

---

## 主要改动

## 后端

### `src/api/services/agent_service.py`

关键改动：

- 通过 `BackgroundRunner` 管理后台 run 生命周期
- 通过 `StreamingSnapshot` 保留断线恢复所需的累计状态
- 事件到快照的聚合逻辑迁移到 `src/api/services/snapshot.py`：
  - `apply_event_to_snapshot()`
- 基于 LangGraph 状态补齐快照的逻辑迁移到 `src/api/services/snapshot.py`：
  - `build_snapshot_from_state()`
- 新增后台执行入口：
  - `start_background_run()`
- 新增订阅入口：
  - `subscribe_to_run()`
- 保留兼容方法：
  - `stream_response()` 仍可直接产生活动事件流，主要用于测试/兼容

实现效果：

- 后台任务持续消费 `_stream_agent_events()`
- 每收到一个事件，就更新内存快照
- 所有在线订阅者都收到同一份 live 事件
- 新订阅者先拿到 `snapshot`

### `src/api/routes/chat.py`

关键改动：

- `POST /api/chat/stream`
  - 不再在请求内直接跑 graph
  - 改为启动后台 run，然后订阅它
- 新增 `GET /api/chat/stream/{session_id}`
  - 用于对同一个会话重新订阅已有后台 run
- 统一通过 `_streaming_response()` 输出标准 SSE

当前接口行为：

- 首次发送消息：`POST /api/chat/stream`
- 断流恢复订阅：`GET /api/chat/stream/{session_id}`

### `src/api/schemas/chat.py`

新增事件类型：

- `snapshot`

它用于返回当前运行快照，不表示新的业务进展，而表示“当前状态全量视图”。

---

## 前端

### `web-ui/lib/stream.ts`

关键改动：

- SSE parser 支持 `snapshot`
- `streamChat()` 发送新消息时附带 `request_id`
- 新增 `resumeChatStream()`
  - 使用 `GET /api/chat/stream/{session_id}` 重新订阅已有 run

### `web-ui/hooks/useWebSocket.ts`

关键改动：

- `sendMessage()` 支持 `requestId`
- 新增 `resumeStream()`
- `resumeStream()` 改为按配置执行多次自动重试与退避
- `StreamConfig` 中增加 `onSnapshot`

### `web-ui/hooks/useChat.ts`

关键改动：

- `initSession()` 不再在页面初始化时强制 reset 旧 session
  - 否则会把可恢复 run 直接清掉
- 新增 `hydrateStreaming(snapshot)`
  - 将 snapshot 恢复为当前前端 streaming 状态

### `web-ui/components/chat/ChatContainer.tsx`

关键改动：

- 处理 `snapshot` 事件
- 发起新消息时，生成并传入 `requestId`
- 初次流请求报错后，尝试对同一个 `session_id` 调用 `resumeStream()`

当前策略是最小实现：

- 如果初次流或恢复中的 SSE 连接断开，前端会自动执行恢复重试
- 每次重连后先拿 snapshot，再继续接收 live 更新
- 重试策略由前端环境变量控制：
  - `NEXT_PUBLIC_STREAM_RESUME_MAX_ATTEMPTS`
  - `NEXT_PUBLIC_STREAM_RESUME_BASE_DELAY_MS`
  - `NEXT_PUBLIC_STREAM_RESUME_BACKOFF_MULTIPLIER`
  - `NEXT_PUBLIC_STREAM_RESUME_MAX_DELAY_MS`
- 默认策略是最多 3 次恢复请求，延迟按 `1000ms -> 2000ms -> 4000ms` 退避，单次延迟上限 5000ms
- 仅对可重试错误自动重试：
  - 网络类异常
  - `408`
  - `429`
  - `5xx`
- 不自动重试：
  - 用户主动 `Abort`
  - `404`（该会话没有可恢复的后台 run）
  - `409`（运行状态冲突）

---

## LangGraph checkpoint 在这个方案中的作用

虽然本次没有把 saver 从内存版切到持久化版，但 LangGraph 的 checkpoint 依然是有价值的。

本次方案中它主要用于：

- 在重连时通过 `agent.get_state(thread_id)` 读取当前 graph 状态
- 用来补齐内存快照里可能尚未完整显式聚合的内容

当前补齐的重点包括：

- `final_report`
- `clarification_status`
- `research_brief`
- `sections`

这意味着即使某些用户可见内容没有完全通过流事件重新播给前端，只要它已经进入 graph state，重连时仍然有机会通过 snapshot 恢复出来。

但要注意：

- 当前 checkpoint 仍是 `MemorySaver`
- 因此它只在当前 Python 进程生命周期内有效

---

## 覆盖的场景

本次实现覆盖的场景如下。

### 已覆盖

#### 场景 1：服务正常运行，SSE 中途断开

例如：

- 浏览器网络短抖动
- 前端页面临时失去连接
- 中间代理把单条 SSE 连接断掉

结果：

- 后台 run 继续执行
- 用户重新订阅同一个 `session_id`
- 后端先返回 snapshot
- 然后继续返回后续 live 事件

#### 场景 2：Deep Research 长任务过程中前端重新连接

例如在 `discover_tools`、`researcher_tools`、`review` 等阶段断流：

- 重新连接后，用户可以看到当前已知的：
  - 部分文本内容
  - 研究大纲
  - clarification question
  - progress node
  - 已经开始/完成的 tool calls

#### 场景 3：用户没有在线订阅，但任务继续在后台跑完

这在测试中已覆盖：

- 即使当前没有 subscriber
- 后台任务仍会执行到底
- 最终 snapshot 会停留在完成态

---

## 未覆盖的场景

本次实现故意没有覆盖下面这些场景。

### 未覆盖 1：服务重启后的恢复

当前使用的是：

- `MemorySaver`
- 内存中的 `BackgroundRun`
- 内存中的 `StreamingSnapshot`

所以只要 Python 进程重启：

- 后台 run 消失
- checkpoint 消失
- snapshot 消失

结果是用户无法恢复这次任务。

### 未覆盖 2：多实例 / 多 worker 场景

当前状态全部在单进程内存里。

所以如果部署为：

- 多个 uvicorn worker
- 多个容器 / 多台机器
- 前面有负载均衡

则重连请求未必落到原来那台实例，恢复能力不成立。

### 未覆盖 3：精确的流式断点续传

当前不是按 SSE event log 做 replay，而是按 snapshot 做恢复。

因此不保证：

- 从上次断开的 token 精确位置继续流
- 重放所有历史 `token` / `progress` / `tool_call_*` 事件
- 完整支持 `Last-Event-ID`

这不是这次方案的目标。

### 未覆盖 4：页面刷新后完整聊天历史恢复

当前恢复重点是“当前运行中的 streaming message”。

没有引入数据库，因此：

- `currentMessages` 的完整持久化历史不保证恢复
- 更像是“当前任务态恢复”，不是“完整对话存档恢复”

### 未覆盖 5：无限重连与更强的网络状态感知

当前前端已经支持有限次自动恢复和指数退避，但仍然没有做：

- 无限次自动重试
- `navigator.onLine` / 浏览器网络事件驱动的更细粒度恢复
- 跨页面刷新后的自动恢复编排

---

## 测试与验证

本次新增/保留的关键验证包括：

- `tests/test_agent_service_keepalive.py`
  - Deep Research 空闲期间仍会发 keepalive
- `tests/test_chat_sse.py`
  - SSE framing 与 comment heartbeat 正确
- `tests/test_agent_service_background_runs.py`
  - 后台 run 在无订阅时也会继续执行
  - 重连订阅时会先收到 snapshot，再收到完成事件

运行命令：

```bash
uv run pytest tests/test_agent_service_keepalive.py tests/test_chat_sse.py tests/test_agent_service_background_runs.py -q
```

前端类型检查：

```bash
cd web-ui
npm exec tsc --noEmit
```

---

## 当前结论

这次实现解决的是：

- “SSE 断了，任务也跟着没了”

改成了：

- “SSE 断了，但后台任务继续跑；用户重连后先拿快照，再继续看到结果”

它是一个明确的最小实现，适合当前阶段验证产品行为和用户体验。

如果后续要覆盖更强的可靠性场景，下一步自然演进方向是：

- 把 `MemorySaver` 换成持久化 saver
- 把 `BackgroundRun` / snapshot 从进程内存迁移到外部存储
- 补页面级历史恢复
- 如果需要，再做真正的事件级 replay
