# 开发者环境搭建

> 面向贡献者和开发者的完整开发环境配置指南

## 开发工具推荐

### VS Code 推荐扩展

以下扩展可以显著提升开发效率:

**Python 后端开发:**

| 扩展 | 说明 |
|------|------|
| Python | Python 语言支持 |
| Pylance | Python 智能补全和类型检查 |
| Ruff | Python 代码格式化和 lint |
| Python Debugger | Python 调试器 |

**前端开发:**

| 扩展 | 说明 |
|------|------|
| ES7+ React/Redux/React-Native snippets | React 代码片段 |
| Tailwind CSS IntelliSense | Tailwind 类名提示 |
| ESLint | JavaScript/TypeScript lint |
| Prettier | 代码格式化 |

**通用工具:**

| 扩展 | 说明 |
|------|------|
| GitLens | Git 增强工具 |
| SQLite Viewer | 数据库查看工具 |
| REST Client | API 测试工具 |
| Markdown Preview Enhanced | Markdown 预览 |

[截图占位]

### VS Code 工作区配置

创建 `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/bin/python",
  "python.analysis.extraPaths": ["${workspaceFolder}/backend"],
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  }
}
```

---

## 后端开发环境

### 1. 创建 Python 虚拟环境

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Linux / macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 安装项目依赖 (含开发工具)
pip install -e ".[dev]"
```

### 2. 配置环境变量

创建 `backend/.env`:

```env
JWT_SECRET_KEY=dev-secret-key-for-local-development-only-32chars
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./data/knowledge.db
CORS_ORIGINS=http://localhost:3000
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-dev-key
```

> **注意**: 开发环境的 JWT 密钥也应至少 32 个字符, 但不要使用生产密钥。

### 3. 运行后端

```bash
cd backend
python -m uvicorn app.main:app --port 8000 --reload
```

`--reload` 参数启用热重载, 修改代码后自动重启服务。

### 4. 运行测试

```bash
cd backend

# 运行所有测试
pytest

# 运行测试并显示覆盖率
pytest --cov=app --cov-report=term-missing

# 运行特定测试文件
pytest tests/test_auth.py -v

# 运行特定测试函数
pytest tests/test_auth.py::test_login -v
```

测试框架配置位于 `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 5. 代码质量

```bash
cd backend

# Ruff lint 检查
ruff check app/

# Ruff 格式化
ruff format app/

# 自动修复
ruff check app/ --fix
```

---

## 前端开发环境

### 1. Node.js 版本管理

推荐使用 nvm (Node Version Manager) 管理 Node.js 版本:

```bash
# 安装 nvm (Linux / macOS)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# 安装 nvm-windows (Windows)
# 从 https://github.com/coreybutler/nvm-windows/releases 下载

# 安装并使用 Node.js 20
nvm install 20
nvm use 20
node --version  # 确认版本 >= 20
```

### 2. 安装依赖

```bash
cd frontend

# 使用 npm
npm install

# 或使用 pnpm (项目包含 pnpm-lock.yaml)
pnpm install
```

### 3. 配置环境变量

创建 `frontend/.env.local`:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 4. 启动开发服务器

```bash
cd frontend
npm run dev
# 或
pnpm dev
```

### 5. ESLint 检查

```bash
cd frontend

# 运行 lint 检查
npm run lint

# ESLint 配置文件: eslint.config.mjs
```

### 6. 前端构建

```bash
cd frontend

# 构建生产版本
npm run build

# 启动生产服务器
npm run start
```

---

## 数据库

### SQLite 自动创建

Knowledge Base 使用 SQLite 数据库, **无需手动创建或配置**:

- 首次启动后端时, 数据库文件自动创建在 `backend/data/knowledge.db`
- 所有表结构通过 SQLAlchemy ORM 自动创建
- 数据库迁移通过 `backend/migrations/` 目录中的脚本管理

### 查看数据库

使用 SQLite CLI 工具:

```bash
cd backend
sqlite3 data/knowledge.db

# 查看所有表
.tables

# 查看表结构
.schema documents

# 退出
.quit
```

或使用 VS Code 的 SQLite Viewer 扩展直接打开 `.db` 文件。

### 手动数据库迁移

如果需要手动修改表结构:

```sql
-- 添加新列
ALTER TABLE documents ADD COLUMN new_field TEXT DEFAULT '';

-- 创建索引
CREATE INDEX idx_documents_status ON documents(status);
```

> **注意**: 生产环境建议通过 `backend/migrations/` 中的迁移脚本管理变更。

---

## 项目结构说明

```
knowledge-base/
  backend/
    app/
      api/            # REST API 路由 (auth, documents, ai, settings...)
      core/           # 核心模块 (config, database, security, limiter)
      mcp/            # MCP 服务端
        tools/        # MCP 工具实现 (search, read, write, analyze, graph, folders)
        server.py     # MCP 服务入口
        stdio_server.py  # Stdio 传输入口
      models/         # SQLAlchemy ORM 模型
      schemas/        # Pydantic 请求/响应模型
      services/       # 业务逻辑层 (LLM, 嵌入, 工作流引擎, 插件加载器)
    plugins/
      builtin/        # 22 个内置插件
      third_party/    # 第三方插件
    tests/            # 测试文件
    data/             # 数据目录 (数据库、上传文件)
    migrations/       # 数据库迁移脚本
  frontend/
    src/              # 前端源代码
    public/           # 静态资源
  electron/           # Electron 桌面端
  docs/               # 文档
```

---

## 调试配置

### VS Code 后端调试

创建 `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend: FastAPI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--port", "8000",
        "--reload"
      ],
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "DEBUG": "true",
        "JWT_SECRET_KEY": "dev-secret-key-for-local-development-only-32chars"
      },
      "jinja": true
    },
    {
      "name": "Backend: Tests",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["-xvs"],
      "cwd": "${workspaceFolder}/backend",
      "justMyCode": false
    }
  ]
}
```

### 前端调试

Next.js 开发服务器自带 Source Maps, 可直接在浏览器 DevTools 或 VS Code 中设置断点调试。

---

## 开发工作流

### 1. 创建功能分支

```bash
git checkout -b feature/my-feature
```

### 2. 开发

- 修改后端代码 -> 自动热重载
- 修改前端代码 -> HMR 自动刷新

### 3. 测试

```bash
# 后端测试
cd backend && pytest

# 前端测试
cd frontend && npx vitest
```

### 4. 提交

```bash
git add .
git commit -m "feat: add new feature"
```
