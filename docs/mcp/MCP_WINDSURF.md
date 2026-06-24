# Windsurf MCP 配置

> 在 Windsurf (Codeium) 编辑器中接入 Knowledge Base

## 前置条件

| 条件 | 说明 |
|------|------|
| Windsurf | 已安装 Windsurf 编辑器 |
| Knowledge Base 后端 | 已在本地或远程运行 |
| Python 3.11+ | 用于 Stdio 模式 |

[截图占位]

## 配置文件位置

Windsurf 的 MCP 配置文件位于:

| 平台 | 路径 |
|------|------|
| macOS / Linux | `~/.codeium/windsurf/mcp_config.json` |
| Windows | `%USERPROFILE%\.codeium\windsurf\mcp_config.json` |

## Stdio 模式配置

### 步骤一: 创建或编辑配置文件

打开 `mcp_config.json` (如果不存在则创建), 添加以下内容:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python",
      "args": ["-m", "app.mcp.stdio_server"],
      "cwd": "/path/to/knowledge-base/backend",
      "env": {
        "JWT_SECRET_KEY": "your-secret-key-at-least-32-chars-long",
        "DATABASE_URL": "sqlite+aiosqlite:///./data/knowledge.db"
      }
    }
  }
}
```

**替换说明**:

| 占位符 | 替换为 |
|--------|--------|
| `/path/to/knowledge-base/backend` | Knowledge Base 后端目录的绝对路径 |
| `your-secret-key-at-least-32-chars-long` | 你的 JWT 密钥 |

### 步骤二: 使用虚拟环境 (推荐)

如果使用 Python 虚拟环境:

**macOS / Linux**:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "/path/to/knowledge-base/backend/.venv/bin/python",
      "args": ["-m", "app.mcp.stdio_server"],
      "cwd": "/path/to/knowledge-base/backend",
      "env": {
        "JWT_SECRET_KEY": "your-secret-key-at-least-32-chars-long"
      }
    }
  }
}
```

**Windows**:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "E:\\tools_creat\\doc\\knowledge-base\\backend\\.venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp.stdio_server"],
      "cwd": "E:\\tools_creat\\doc\\knowledge-base\\backend",
      "env": {
        "JWT_SECRET_KEY": "your-secret-key-at-least-32-chars-long"
      }
    }
  }
}
```

### 步骤三: 重启 Windsurf

保存配置文件后, 重启 Windsurf 编辑器。

---

## SSE 模式配置

如果 Knowledge Base 后端已在运行:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "url": "http://localhost:8000/mcp/sse",
      "headers": {
        "Authorization": "Bearer YOUR_JWT_TOKEN"
      }
    }
  }
}
```

获取 Token:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

---

## 验证连接

### 检查 MCP 服务器状态

1. 打开 Windsurf
2. 打开 Cascade (AI 助手面板)
3. 输入: "列出知识库中的所有文件夹"
4. 如果 Cascade 成功调用 `list_folders` 工具, 说明配置成功

### 检查工具列表

在 Cascade 中输入:

> "你可以使用哪些知识库工具?"

Cascade 应该列出所有可用的 MCP 工具。

[截图占位]

---

## 在 Windsurf 中使用知识库

### Cascade 中使用

在 Cascade 面板中直接对话:

> "搜索知识库中与'用户认证'相关的文档, 阅读第一篇, 帮我总结关键要点"

### 代码注释生成

> "读取知识库中的'代码规范'文档, 然后为当前文件添加符合规范的注释"

### 文档同步

> "将当前文件的内容保存到知识库的'技术文档'文件夹中, 标题为文件名"

---

## 常见问题

### MCP 配置不生效

1. 确认配置文件路径: `~/.codeium/windsurf/mcp_config.json`
2. 确认 JSON 格式正确
3. 完全退出并重新打开 Windsurf

### 权限问题 (macOS)

macOS 可能需要授权 Windsurf 访问磁盘:

系统设置 -> 隐私与安全 -> 完全磁盘访问权限 -> 添加 Windsurf

### Python 路径问题

如果 `python` 命令找不到, 使用完整路径:

```bash
# 查找 Python 路径
which python3  # macOS/Linux
where python   # Windows
```

然后将配置文件中的 `python` 替换为完整路径。
