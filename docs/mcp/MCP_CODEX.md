# OpenAI Codex / ChatGPT MCP 配置

> 在 OpenAI Codex 或 ChatGPT 中接入 Knowledge Base

## 概述

OpenAI 的 MCP 客户端支持允许 Codex 和 ChatGPT 通过 MCP 协议连接外部工具和数据源。本文档介绍如何将 Knowledge Base 连接到 OpenAI 的 MCP 客户端。

> **注意**: OpenAI 的 MCP 客户端功能可能仍在逐步推出中, 部分功能可能因版本差异而有所不同。

[截图占位]

## 前置条件

| 条件 | 说明 |
|------|------|
| OpenAI 账号 | 具有 MCP 客户端访问权限 |
| Knowledge Base 后端 | 已在可访问的服务器上运行 |
| 网络连通 | 确保 OpenAI 客户端可以访问你的 MCP 端点 |

---

## SSE 模式配置 (推荐)

OpenAI 的 MCP 客户端主要支持 SSE 传输模式, 因为 Stdio 模式需要本地子进程权限。

### 步骤一: 确保后端服务可访问

Knowledge Base 后端需要运行在 OpenAI 客户端可以访问的地址上:

- **公网服务器**: 使用域名或公网 IP
- **本地开发**: 使用 ngrok 等工具暴露本地端口

使用 ngrok 暴露本地服务:

```bash
# 安装 ngrok
# https://ngrok.com/download

# 暴露后端服务
ngrok http 8000
```

记录下 ngrok 提供的公网 URL (如 `https://xxxx.ngrok-free.app`)。

### 步骤二: 配置 MCP 服务器

在 OpenAI MCP 客户端中添加服务器:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "url": "https://your-server.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer YOUR_JWT_TOKEN"
      }
    }
  }
}
```

**替换说明**:

| 占位符 | 替换为 |
|--------|--------|
| `https://your-server.com` | 你的后端服务地址 (或 ngrok URL) |
| `YOUR_JWT_TOKEN` | 有效的 JWT Token |

### 步骤三: 获取 JWT Token

```bash
curl -X POST https://your-server.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

> **安全提示**: Token 有过期时间 (默认 15 分钟), 建议使用 Refresh Token 或在服务器端设置更长的过期时间。

---

## ChatGPT Connectors (替代方案)

如果你的 ChatGPT 版本支持 Connectors 功能, 也可以通过自定义 API 方式接入:

### 方式: 使用 OpenAPI Schema

Knowledge Base 在 DEBUG 模式下会暴露 OpenAPI Schema (`/api/openapi.json`), 可以用于创建 ChatGPT Action:

1. 启动后端并开启 DEBUG 模式
2. 访问 `http://localhost:8000/api/openapi.json` 获取 Schema
3. 在 ChatGPT 的 GPT Builder 中导入 Schema
4. 配置 Authentication 为 Bearer Token

---

## 兼容性说明

### 已验证功能

| 功能 | 兼容性 |
|------|--------|
| SSE 传输 | 支持 |
| Bearer Token 认证 | 支持 |
| 文档搜索 | 支持 |
| 文档读取 | 支持 |
| 文档创建/编辑 | 支持 |
| 知识图谱查询 | 支持 |
| Stdio 传输 | 不支持 (需本地进程权限) |

### 已知限制

1. **Token 过期**: OpenAI 客户端不会自动刷新 JWT Token, Token 过期后需手动更新
2. **网络延迟**: 远程服务器的响应时间可能影响体验
3. **数据隐私**: 通过公网传输的数据请确保使用 HTTPS

---

## 安全建议

1. **使用 HTTPS**: 确保 MCP 端点使用 SSL/TLS 加密
2. **限制 CORS**: 仅允许必要的源访问
3. **定期轮换 Token**: 避免长期使用同一 Token
4. **速率限制**: 配置合理的速率限制防止滥用

```nginx
# Nginx HTTPS 配置示例
server {
    listen 443 ssl;
    server_name kb-api.your-domain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

---

## 常见问题

### 连接失败: 无法访问 MCP 端点

- 确认后端服务正在运行
- 确认服务器防火墙允许入站连接
- 如果使用 ngrok, 确认 ngrok 进程仍在运行

### 认证失败: 401 Unauthorized

- 检查 JWT Token 是否已过期
- 确认 Token 格式正确 (`Bearer <token>`)
- 重新登录获取新 Token

### 工具列表为空

- 确认 MCP 服务器版本是最新的
- 检查 SSE 连接是否正常建立
- 查看后端日志排查错误
