# Claude Desktop MCP 配置

> 在 Claude Desktop 中接入 Knowledge Base, 让 Claude 直接操作你的知识库

## 前置条件

| 条件 | 说明 |
|------|------|
| Claude Desktop | 已安装 Claude Desktop 应用 |
| Knowledge Base 后端 | 已在本地或远程运行 |
| Python 3.11+ | 用于 Stdio 模式 (本地运行) |

[截图占位]

## 配置方式

Claude Desktop 支持两种 MCP 连接方式:

- **Stdio 模式**: Claude Desktop 直接启动本地 Python 进程 (推荐本地使用)
- **SSE 模式**: 连接到已运行的远程 MCP 服务 (推荐远程服务器)

---

## Stdio 模式配置 (推荐)

### 步骤一: 找到配置文件位置

Claude Desktop 的 MCP 配置文件位置:

| 平台 | 路径 |
|------|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### 步骤二: 编辑配置文件

打开 `claude_desktop_config.json`, 添加以下内容:

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

**重要**: 将以下内容替换为你的实际值:

| 占位符 | 替换为 |
|--------|--------|
| `/path/to/knowledge-base/backend` | 你的 Knowledge Base 后端目录的**绝对路径** |
| `your-secret-key-at-least-32-chars-long` | 你的 JWT 密钥 (与 `.env` 文件中保持一致) |

> **Windows 路径注意**: Windows 路径使用双反斜杠或正斜杠:
> ```json
> "cwd": "E:\\tools_creat\\doc\\knowledge-base\\backend"
> ```
> 或
> ```json
> "cwd": "E:/tools_creat/doc/knowledge-base/backend"
> ```

### 步骤三: 配置 Python 路径 (可选)

如果使用虚拟环境, 需要指定 Python 路径:

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

**Windows 虚拟环境**:

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

### 步骤四: 重启 Claude Desktop

**完全退出** Claude Desktop 后重新打开:

- macOS: `Cmd + Q` 退出
- Windows: 右键托盘图标 -> 退出

重新打开后, 在聊天界面中应该能看到 MCP 工具列表。

---

## SSE 模式配置

如果你已经在运行 Knowledge Base 后端服务, 可以使用 SSE 模式直接连接。

### 配置

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

### 获取 JWT Token

在终端运行:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

从响应中复制 `access_token` 值, 替换配置中的 `YOUR_JWT_TOKEN`。

> **注意**: SSE 模式需要后端服务持续运行。先启动后端:
> ```bash
> cd backend
> python -m uvicorn app.main:app --port 8000
> ```

---

## 验证连接

### 检查工具列表

重启 Claude Desktop 后:

1. 开始一个新对话
2. 点击聊天框左侧的 "工具" (Tools) 图标
3. 确认 `knowledge-base` 出现在 MCP 服务器列表中
4. 展开查看可用工具列表

[截图占位]

你应该能看到以下工具:

- `search_documents`
- `read_document`
- `list_documents`
- `create_document`
- `update_document`
- `delete_document`
- `move_document`
- `manage_tags`
- `summarize_document`
- `search_knowledge_graph`
- `list_folders`
- `list_tags`

### 测试对话

在 Claude Desktop 中尝试以下对话:

> "列出我知识库中的所有文件夹"

如果 Claude 成功调用 `list_folders` 工具并返回结果, 说明配置成功!

> "搜索知识库中关于'Python'的文档"

如果返回搜索结果, 说明知识库连接完全正常。

---

## 常见问题

### Claude Desktop 中没有看到 MCP 工具

1. 确认配置文件路径正确
2. 确认 JSON 格式无误 (可用 JSON 校验工具检查)
3. 确认 `cwd` 路径指向正确的 backend 目录
4. 完全退出 Claude Desktop 后重新打开 (不是最小化)

### 工具调用失败: ModuleNotFoundError

Python 环境中缺少依赖:

```bash
cd /path/to/knowledge-base/backend
pip install -e .
```

### 工具调用失败: 数据库错误

确保 `DATABASE_URL` 指向正确的数据库文件:

```json
"env": {
  "DATABASE_URL": "sqlite+aiosqlite:///./data/knowledge.db"
}
```

### macOS 权限问题

macOS 可能需要授予 Claude Desktop 磁盘访问权限:

系统设置 -> 隐私与安全 -> 完全磁盘访问权限 -> 添加 Claude Desktop
