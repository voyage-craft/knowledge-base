# Cursor IDE MCP 配置

> 在 Cursor 编辑器中接入 Knowledge Base, 让 AI 助手直接操作你的知识库

## 前置条件

| 条件 | 说明 |
|------|------|
| Cursor IDE | 已安装 Cursor 编辑器 |
| Knowledge Base 后端 | 已在本地或远程运行 |
| Python 3.11+ | 用于 Stdio 模式 |

[截图占位]

## 配置方式

Cursor 支持通过两种方式配置 MCP:

1. **项目级配置**: `.cursor/mcp.json` (仅对当前项目生效)
2. **全局配置**: Cursor Settings -> MCP

---

## Stdio 模式配置

### 方式一: 项目级配置 (推荐)

在项目根目录创建 `.cursor/mcp.json`:

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

**使用虚拟环境**:

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

**Windows 路径**:

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

### 方式二: 全局配置

1. 打开 Cursor Settings (`Ctrl/Cmd + ,`)
2. 搜索 "MCP"
3. 点击 "Add MCP Server"
4. 填写服务器信息:
   - **Name**: `knowledge-base`
   - **Type**: `stdio`
   - **Command**: `python -m app.mcp.stdio_server`
   - **Working Directory**: 你的 backend 目录
5. 添加环境变量:
   - `JWT_SECRET_KEY`: 你的 JWT 密钥
   - `DATABASE_URL`: 数据库路径

[截图占位]

---

## SSE 模式配置

如果你的 Knowledge Base 后端已经在运行:

### 项目级配置

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

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

---

## 验证连接

### 步骤一: 检查 MCP 状态

1. 打开 Cursor
2. 按 `Ctrl/Cmd + Shift + P` 打开命令面板
3. 搜索 "MCP" 查看 MCP 服务器状态
4. 确认 `knowledge-base` 显示为 "Connected"

### 步骤二: 测试工具调用

在 Cursor 的 AI Chat 中 (Ctrl/Cmd + L):

> "列出我知识库中的所有标签"

如果 AI 调用了 `list_tags` 工具并返回结果, 配置成功!

### 步骤三: 在代码编辑中使用

在编辑器中选中代码, 按 `Ctrl/Cmd + K`, 可以请求 AI:

> "将这段代码的解释保存为知识库文档, 标题为'代码说明'"

---

## Cursor 专属功能

### Composer 中使用

在 Cursor Composer 中可以组合使用代码编辑和知识库操作:

> "阅读知识库中'API 设计规范'文档, 然后根据规范检查当前打开的文件"

### Agent 模式

在 Cursor Agent 模式下, AI 可以自动调用多个 MCP 工具完成复杂任务:

> "搜索知识库中所有标记为'待审核'的文档, 为每篇文档生成摘要, 然后将结果保存到'摘要'文件夹"

---

## 常见问题

### MCP 服务器连接失败

1. 检查 `.cursor/mcp.json` 文件语法是否正确
2. 确认 `cwd` 路径存在且正确
3. 确认 Python 环境已安装所需依赖
4. 查看 Cursor 的 MCP 日志排查详细错误

### Python 找不到模块

确保使用正确的 Python 路径:

```bash
# 检查 Python 路径
which python  # macOS/Linux
where python  # Windows

# 如果使用虚拟环境, 使用虚拟环境中的 Python
/path/to/.venv/bin/python  # macOS/Linux
/path/to/.venv/Scripts/python.exe  # Windows
```

### 工具调用超时

- Stdio 模式: 首次调用时可能需要加载嵌入模型, 稍等片刻
- SSE 模式: 检查后端服务是否正常运行
