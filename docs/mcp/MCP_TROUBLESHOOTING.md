# MCP 故障排查

> MCP 集成常见问题与解决方案

## 快速诊断

在排查问题之前, 先确认以下基本事项:

| 检查项 | 命令/方法 |
|--------|-----------|
| 后端服务运行中? | 访问 http://localhost:8000/api/health |
| Python 版本正确? | `python --version` (需要 3.11+) |
| 依赖已安装? | `cd backend && pip install -e .` |
| 数据库存在? | 检查 `backend/data/knowledge.db` 是否存在 |
| JWT 密钥已设置? | 确认 `.env` 或配置文件中有 `JWT_SECRET_KEY` |

---

## 常见问题及解决方案

### 1. 连接被拒绝 (Connection Refused)

**症状**: AI 客户端提示无法连接到 MCP 服务器。

**原因**: MCP 服务没有运行。

**解决方案**:

**SSE 模式**: 确认后端服务正在运行:

```bash
cd backend
python -m uvicorn app.main:app --port 8000

# 验证
curl http://localhost:8000/api/health
# 应返回: {"status": "ok"}
```

**Stdio 模式**: 确认 Python 路径和 `cwd` 配置正确:

```bash
# 手动测试 Stdio 服务器是否能启动
cd /path/to/knowledge-base/backend
python -m app.mcp.stdio_server
# 如果正常启动, 按 Ctrl+C 退出
```

如果手动启动失败, 检查:
- `cwd` 路径是否指向正确的 `backend/` 目录
- Python 是否已安装项目依赖

---

### 2. 401 Unauthorized (认证失败)

**症状**: SSE 模式下工具调用返回 401 错误。

**原因**: Bearer Token 无效、过期或缺失。

**解决方案**:

1. 确认配置中包含 `Authorization` 头:

```json
{
  "headers": {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."
  }
}
```

2. 获取新的 Token:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

3. 复制响应中的 `access_token` 值替换旧 Token

4. 如果 Token 频繁过期, 可以延长有效期:

```env
# backend/.env
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 小时
```

> **注意**: Stdio 模式不需要 Bearer Token。

---

### 3. Tool Not Found (工具未找到)

**症状**: AI 客户端尝试调用工具时提示工具不存在。

**原因**: MCP 服务器版本过旧或工具未正确注册。

**解决方案**:

1. 确认使用最新版本的代码:

```bash
cd /path/to/knowledge-base
git pull
cd backend
pip install -e .
```

2. 手动验证工具是否已注册:

```python
# 在 backend 目录下运行
python -c "
from app.mcp.server import mcp
tools = mcp._tool_manager._tools
for name in sorted(tools.keys()):
    print(f'  - {name}')
"
```

应该输出:

```
  - create_document
  - delete_document
  - list_documents
  - list_folders
  - list_tags
  - manage_tags
  - move_document
  - read_document
  - search_documents
  - search_knowledge_graph
  - summarize_document
  - update_document
```

---

### 4. 超时错误 (Timeout)

**症状**: 工具调用超时, 长时间没有返回结果。

**原因**: 网络问题、首次加载模型、或数据库过大。

**解决方案**:

**首次调用慢**: 嵌入模型在首次使用时需要下载和加载, 可能需要 30-60 秒:

```bash
# 预加载嵌入模型
cd backend
python -c "
from app.services.embedding_service import embedding_service
import asyncio
asyncio.run(embedding_service.get_embedding('test'))
print('Embedding model loaded!')
"
```

**网络问题**: 检查网络连通性:

```bash
# SSE 模式: 测试网络
curl -v http://localhost:8000/mcp/sse

# 如果通过代理访问, 确认代理配置正确
```

**数据库过大**: 对于大量文档, 语义搜索可能较慢:

```bash
# 检查数据库大小
ls -lh backend/data/knowledge.db

# 搜索时减少 top_k 值
# search_documents(query="...", top_k=3)
```

---

### 5. ModuleNotFoundError (模块未找到)

**症状**: Stdio 模式启动时提示找不到模块。

**原因**: Python 环境中缺少项目依赖。

**解决方案**:

```bash
cd /path/to/knowledge-base/backend

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .

# 验证
python -m app.mcp.stdio_server
```

如果使用虚拟环境, 在 MCP 配置中指定虚拟环境的 Python:

```json
{
  "command": "/path/to/knowledge-base/backend/.venv/bin/python",
  "args": ["-m", "app.mcp.stdio_server"],
  "cwd": "/path/to/knowledge-base/backend"
}
```

---

### 6. 数据库错误

**症状**: 工具调用时返回数据库相关错误。

**原因**: 数据库文件不存在或路径配置错误。

**解决方案**:

```bash
# 检查数据库文件是否存在
ls -la backend/data/knowledge.db

# 如果不存在, 启动后端自动创建
cd backend
python -m uvicorn app.main:app --port 8000

# 确认 DATABASE_URL 配置正确
# Stdio 模式需要在 env 中设置:
"env": {
  "DATABASE_URL": "sqlite+aiosqlite:///./data/knowledge.db"
}
```

---

### 7. JSON 配置文件语法错误

**症状**: AI 客户端无法解析 MCP 配置。

**原因**: JSON 文件格式错误。

**解决方案**:

常见错误:

```json
// 错误: 使用了注释
{
  // 这是注释, JSON 不支持!
  "mcpServers": {}
}

// 错误: 末尾多余逗号
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python",
    }  // <-- 这里的逗号是多余的
  }
}

// 错误: Windows 路径使用单反斜杠
{
  "cwd": "C:\Users\name\project"  // 应该用双反斜杠或正斜杠
}
```

正确格式:

```json
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python",
      "args": ["-m", "app.mcp.stdio_server"],
      "cwd": "C:/Users/name/project/backend"
    }
  }
}
```

使用 JSON 校验工具检查: https://jsonlint.com/

---

## 查看日志

### 后端日志

```bash
# 查看后端日志 (SSE 模式)
cd backend
python -m uvicorn app.main:app --port 8000 --log-level debug
```

### Stdio 日志

Stdio 模式的日志通常输出到 AI 客户端的 MCP 日志面板。

### Claude Desktop 日志

```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Windows
type "%APPDATA%\Claude\logs\mcp*.log"
```

---

## 诊断检查清单

按顺序检查以下项目:

- [ ] Python 版本 >= 3.11
- [ ] 项目依赖已安装 (`pip install -e .`)
- [ ] `.env` 文件中设置了 `JWT_SECRET_KEY`
- [ ] 后端服务正在运行 (`/api/health` 返回 ok)
- [ ] 数据库文件存在 (`backend/data/knowledge.db`)
- [ ] MCP 配置文件 JSON 格式正确
- [ ] `cwd` 路径指向正确的 backend 目录
- [ ] AI 客户端已重启
- [ ] 防火墙/代理没有阻止连接

如果以上都确认无误但问题仍然存在, 请提供以下信息以便进一步排查:

1. Python 版本
2. 操作系统
3. AI 客户端名称和版本
4. MCP 配置文件内容 (脱敏后)
5. 错误信息全文
6. 后端日志
