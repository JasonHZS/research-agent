# 部署网络访问问题排查与解决

本文档整理 Research Agent 部署到云服务器后，从无法访问到稳定运行的全过程排查与解决方案。

## 环境概览

- **服务器**：云服务器（如腾讯云轻量应用服务器）
- **公网 IP**：`YOUR_SERVER_IP`（部署时替换为实际 IP）
- **域名**：`your-domain.com`（前端）、`api.your-domain.com`（API）
- **DNS**：Cloudflare（或其他 DNS 服务商）
- **服务**：Next.js 前端（3000）、Python API（8111）、Caddy 反向代理

---

## 1. 端口与监听状态

### 1.1 检查当前监听端口

```bash
ss -tlnp
```

**对外开放端口**：22（SSH）、3000（Next.js）、8111（API）  
**仅本地**：53（DNS）、Node/Cursor 内部端口

### 1.2 云防火墙（安全组）

云服务器需在控制台单独放行端口，本机监听 `0.0.0.0` 不代表外网可访问。

**必须放行**：

- TCP 80（HTTP）
- TCP 443（HTTPS）
- TCP 22（SSH，通常默认已有）

路径：云服务器控制台 → 防火墙 → 添加规则

---

## 2. 域名无法访问

### 2.1 现象

DNS 已正确解析（A 记录指向服务器 IP），但浏览器访问域名无响应。

### 2.2 原因

浏览器访问 `https://your-domain.com` 时，请求发往 **80/443 端口**，而 Next.js 和 API 分别监听 3000、8111，没有服务在 80/443 上接收请求。

### 2.3 解决：安装 Caddy 反向代理

```bash
sudo apt-get install -y caddy
```

**Caddyfile 配置**（`/etc/caddy/Caddyfile`）：

```
your-domain.com {
    reverse_proxy localhost:3000
}

api.your-domain.com {
    reverse_proxy localhost:8111
}
```

```bash
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

Caddy 会自动申请 Let's Encrypt 证书，启用 HTTPS。

---

## 3. Next.js Standalone 模式问题

### 3.1 Clerk secretKey 缺失

**现象**：`@clerk/nextjs: Missing secretKey`

**原因**：`node .next/standalone/server.js` 不会自动加载 `.env.local`。

**解决**：使用 `dotenv-cli` 启动：

```bash
npm install --save-dev dotenv-cli
```

在 `package.json` 添加：

```json
"start:prod": "dotenv -e .env.local -- node .next/standalone/server.js"
```

### 3.2 静态资源 404

**现象**：`/_next/static/css/*.css`、`/_next/static/chunks/*.js` 等返回 404。

**原因**：Standalone 模式只打包服务端代码，不包含 `.next/static`。

**解决**：每次 build 后复制静态文件：

```bash
cp -r .next/static .next/standalone/.next/static
```

建议加入构建脚本或 CI 流程。

---

## 4. Cloudflare 代理配置

### 4.1 橙云 vs 灰云


| 状态        | 说明                         |
| --------- | -------------------------- |
| 灰云（仅 DNS） | 直连源站，无 CDN                 |
| 橙云（已代理）   | 经 Cloudflare CDN，可加速、隐藏 IP |


### 4.2 开启橙云前必须设置

**SSL 模式**：Cloudflare 控制台 → SSL/TLS → 加密模式选 **「完全 (Full)」**

若保持「灵活 (Flexible)」，Cloudflare 到源站走 HTTP，而 Caddy 强制 HTTPS，会导致 `ERR_TOO_MANY_REDIRECTS`。

### 4.3 SSE 与 Cloudflare 缓冲

**重要**：Cloudflare 免费版会缓冲 SSE 响应，导致流式输出延迟或断连。

**建议**：

- 前端域名：可开橙云，享受 CDN
- API 子域名（如 `api.your-domain.com`）：保持**灰云**，直连服务器

---

## 5. SSE 通信不稳定

### 5.1 现象

聊天流式输出中途断开，或长时间无响应。

### 5.2 原因

生产环境下，API 请求路径为：

```
浏览器 → Cloudflare → Caddy → Next.js rewrite → Python API
```

经过多层代理，任一层缓冲或超时都会导致 SSE 断连。

### 5.3 解决：API 直连

让前端直接请求 API 域名（如 `https://api.your-domain.com`），绕过 Next.js 代理。

**1. 修改 `web-ui/lib/utils.ts`**：

```typescript
export function getApiBaseUrl(): string {
  if (typeof window === 'undefined') return '';

  if (process.env.NODE_ENV === 'development') return 'http://localhost:8111';

  return process.env.NEXT_PUBLIC_API_URL ?? window.location.origin;
}
```

**2. 配置 `web-ui/.env.local`**：

```
NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

**3. 重新构建并启动**：

```bash
npm run build
cp -r .next/static .next/standalone/.next/static
npm run start:prod
```

确保 API 子域名为灰云，避免 Cloudflare 缓冲 SSE。

---

## 6. 其他问题

### 6.1 .env 解析警告

**现象**：`python-dotenv could not parse statement starting at line 47`

**原因**：注释行缺少 `#` 前缀。

**解决**：将 `Feed digest force refresh security...` 改为 `# Feed digest force refresh security...`

### 6.2 feeds/digest 超时

**现象**：`socket hang up`，Next.js 代理报错。

**原因**：digest 生成需约 4 分钟，Next.js rewrite 默认超时约 30 秒。

**解决**：为 `/api/feeds/digest` 创建独立 API 路由，设置 `maxDuration = 300`，直接转发到后端。

### 6.3 Content Reader 子 Agent 卡住

**现象**：`task` 工具调用 content-reader-agent 后长时间无响应。

**可能原因**：OpenRouter/LLM 调用延迟、网络波动、目标 URL 抓取慢。Jina Reader 连通性可单独用 curl 验证。

---

## 7. 部署检查清单

- [ ] 云防火墙放行 80、443、22
- [ ] Caddy 已安装并配置 Caddyfile
- [ ] Next.js 使用 `npm run start:prod` 启动（加载 .env.local）
- [ ] 已执行 `cp -r .next/static .next/standalone/.next/static`
- [ ] Cloudflare SSL 模式为「完全」
- [ ] API 子域名保持灰云（若使用 SSE）
- [ ] `NEXT_PUBLIC_API_URL` 已配置并重新 build

---

## 8. 常用诊断命令

```bash
# 检查端口监听
ss -tlnp | grep -E ':80|:443|:3000|:8111'

# 测试 HTTPS
curl -sv https://your-domain.com

# 测试 API
curl -s https://api.your-domain.com/api/models

# 查看 Caddy 状态
systemctl status caddy
```
