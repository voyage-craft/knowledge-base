# 快速开始

> 5 分钟内在本地运行 Knowledge Base 系统

## 环境要求

在开始之前, 请确保你的开发环境满足以下条件:

| 依赖 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 20+ | 前端运行环境 |
| pip | 最新版 | Python 包管理器 (随 Python 安装) |
| npm | 最新版 | Node.js 包管理器 (随 Node.js 安装) |

> **提示**: 可使用 `python --version` 和 `node --version` 检查已安装的版本。

## 第一步: 克隆项目

```bash
git clone <repository-url> knowledge-base
cd knowledge-base
```

## 第二步: 配置后端

### 2.1 创建环境变量文件

进入 `backend/` 目录, 创建 `.env` 文件:

```bash
cd backend
cp .env.example .env  # 如果有示例文件
```

手动创建 `.env` 文件, 写入以下内容:

```env
# JWT 密钥 -- 必须设置, 至少 32 个字符
JWT_SECRET_KEY=your-strong-secret-key-at-least-32-chars-long

# 调试模式 (开发环境建议开启)
DEBUG=true

# 数据库路径 (默认即可, 自动创建)
DATABASE_URL=sqlite+aiosqlite:///./data/knowledge.db

# CORS 允许的源
CORS_ORIGINS=http://localhost:3000

# LLM 服务商 (可选, 默认 openai)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key
```

> **生成安全密钥**: 运行以下命令生成随机密钥:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(48))"
> ```

### 2.2 安装后端依赖

```bash
cd backend
pip install -e .
```

如需安装开发依赖 (测试、lint 等):

```bash
pip install -e ".[dev]"
```

如需安装 AI 嵌入模型依赖:

```bash
pip install -e ".[ai]"
```

## 第三步: 启动后端服务

```bash
cd backend
python -m uvicorn app.main:app --port 8000
```

启动成功后, 你将看到类似输出:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application started. Embedding model will load on first use.
```

> **验证**: 访问 http://localhost:8000/api/health , 如果返回 `{"status": "ok"}` 说明后端启动成功。

## 第四步: 安装并启动前端

打开新的终端窗口:

```bash
cd frontend
npm install
npx next dev --port 3000
```

> 如果使用 pnpm:
> ```bash
> cd frontend
> pnpm install
> pnpm dev --port 3000
> ```

启动成功后:

```
  ▲ Next.js 16.x.x
  - Local:        http://localhost:3000
```

## 第五步: 登录系统

打开浏览器访问 http://localhost:3000 , 使用默认管理员账号登录:

| 字段 | 值 |
|------|-----|
| 用户名 | `admin` |
| 密码 | `admin123` |

> **安全提示**: 首次登录后请立即修改默认密码!

[截图占位]

## 快速验证清单

完成以上步骤后, 确认以下功能正常:

- [ ] 后端健康检查: http://localhost:8000/api/health 返回 `{"status": "ok"}`
- [ ] 前端页面加载: http://localhost:3000 可以正常访问
- [ ] 管理员登录: 使用 admin / admin123 成功登录
- [ ] 创建文档: 在首页点击"新建文档"可以正常创建
- [ ] AI 功能: 在设置中配置 LLM API Key 后, AI 功能可用

## 常见问题

### 后端启动失败: JWT_SECRET_KEY 相关错误

确保 `.env` 文件中设置了 `JWT_SECRET_KEY`, 且长度不少于 32 个字符。不要使用已知的弱密钥值 (如 `secret`, `change-me` 等)。

### 前端连接后端失败

确认:
1. 后端已在 8000 端口运行
2. `.env` 中 `CORS_ORIGINS` 包含 `http://localhost:3000`
3. 前端环境变量中后端地址指向 `http://localhost:8000`

### pip install 失败

尝试使用国内镜像源:

```bash
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 下一步

- 阅读 [系统配置](../configuration/SYSTEM_CONFIG.md) 了解更多配置选项
- 阅读 [LLM 服务商配置](../configuration/LLM_PROVIDERS.md) 接入 AI 模型
- 阅读 [MCP 集成指南](../mcp/MCP_OVERVIEW.md) 将知识库连接到编辑器
