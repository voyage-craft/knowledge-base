# Electron 桌面端安装指南

> Knowledge Base 桌面客户端基于 Electron 构建, 提供原生桌面体验

## 系统要求

| 平台 | 最低版本 |
|------|----------|
| Windows | Windows 10 (64 位) 及以上 |
| macOS | macOS 12 (Monterey) 及以上 |
| Linux | Ubuntu 20.04 / Fedora 36 及以上 |

## 下载安装

### 方式一: 从发布页下载 (推荐)

1. 访问项目的 [Releases 页面](../../releases)
2. 下载对应平台的安装包:
   - **Windows**: `Knowledge-Base-Setup-x.x.x.exe`
   - **macOS**: `Knowledge-Base-x.x.x.dmg`
   - **Linux**: `knowledge-base-x.x.x.AppImage`
3. 运行安装包并按照安装向导完成安装

[截图占位]

### 方式二: 从源码构建

```bash
cd electron
npm install
npm run build
```

构建产物位于 `electron/dist/` 目录。

## Windows 安装步骤

1. 双击 `.exe` 安装文件
2. 如果 Windows Defender SmartScreen 弹出警告, 点击"更多信息" -> "仍要运行"
3. 按照安装向导选择安装路径 (默认为 `C:\Users\<用户名>\AppData\Local\Knowledge Base\`)
4. 点击"安装"开始安装
5. 安装完成后, 勾选"立即运行"并点击"完成"

## 首次启动

### 配置文件

首次启动时, 应用会在以下位置自动创建配置目录:

| 平台 | 配置路径 |
|------|----------|
| Windows | `%APPDATA%\knowledge-base\` |
| macOS | `~/Library/Application Support/knowledge-base/` |
| Linux | `~/.config/knowledge-base/` |

配置目录结构:

```
knowledge-base/
  config.json       # 应用配置 (后端地址、窗口设置等)
  logs/             # 应用日志
  cache/            # 本地缓存
```

### 连接后端服务

首次启动后, 需要配置后端服务地址:

1. 在欢迎界面输入后端服务地址
2. 默认地址: `http://localhost:8000`
3. 如果是远程服务器, 输入服务器的 IP 或域名: `http://your-server:8000`
4. 点击"连接"进行验证

[截图占位]

### 登录

使用与 Web 端相同的账号登录:

| 字段 | 默认值 |
|------|--------|
| 用户名 | `admin` |
| 密码 | `admin123` |

## 系统托盘

Knowledge Base 桌面端支持系统托盘驻留:

- **Windows**: 在任务栏右下角的通知区域显示托盘图标
- **macOS**: 在菜单栏显示托盘图标
- **Linux**: 在系统托盘中显示图标 (需桌面环境支持)

### 托盘菜单

右键点击托盘图标可以使用以下功能:

| 菜单项 | 说明 |
|--------|------|
| 打开主窗口 | 显示 Knowledge Base 主界面 |
| 快速搜索 | 打开全局搜索窗口 |
| 新建文档 | 快速创建新文档 |
| 最近文档 | 查看最近编辑的文档列表 |
| 设置 | 打开应用设置 |
| 检查更新 | 检查是否有新版本 |
| 退出 | 完全关闭应用 |

> **提示**: 关闭窗口时应用默认最小化到托盘而非退出。可在设置中修改此行为。

## 应用设置

通过 `Ctrl + ,` (Windows/Linux) 或 `Cmd + ,` (macOS) 打开设置:

### 通用设置

| 设置项 | 说明 | 默认值 |
|--------|------|--------|
| 开机自启动 | 系统启动时自动运行应用 | 关闭 |
| 关闭窗口时最小化到托盘 | 点击关闭按钮时隐藏到托盘 | 开启 |
| 主题 | 亮色 / 暗色 / 跟随系统 | 跟随系统 |
| 语言 | 界面语言 | 中文 |

### 连接设置

| 设置项 | 说明 | 默认值 |
|--------|------|--------|
| 后端地址 | API 服务地址 | `http://localhost:8000` |
| 自动重连 | 断线后自动尝试重连 | 开启 |
| 代理设置 | HTTP 代理地址 | 空 |

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl/Cmd + N` | 新建文档 |
| `Ctrl/Cmd + O` | 打开文档 |
| `Ctrl/Cmd + S` | 保存文档 |
| `Ctrl/Cmd + P` | 快速搜索 |
| `Ctrl/Cmd + F` | 文档内搜索 |
| `Ctrl/Cmd + ,` | 打开设置 |
| `Ctrl/Cmd + Q` | 退出应用 |

## 更新

### 自动更新

应用内置自动更新功能:

1. 应用启动时自动检查更新
2. 发现新版本时在托盘图标上显示提示
3. 点击提示下载安装包
4. 下载完成后提示重启安装

### 手动更新

1. 访问 Releases 页面下载新版本安装包
2. 运行新版本安装包 (会自动覆盖旧版本)
3. 重启应用即可

## 卸载

### Windows

- 方式一: 设置 -> 应用 -> 找到 "Knowledge Base" -> 卸载
- 方式二: 运行安装目录下的 `Uninstall Knowledge Base.exe`

### 清理配置数据 (可选)

卸载后, 如需完全清除所有数据:

```
# Windows
rmdir /s /q "%APPDATA%\knowledge-base"

# macOS
rm -rf ~/Library/Application\ Support/knowledge-base

# Linux
rm -rf ~/.config/knowledge-base
```

## 常见问题

### 安装后无法启动

- 检查系统版本是否满足最低要求
- 尝试以管理员身份运行
- 查看日志文件: `%APPDATA%\knowledge-base\logs\`

### 无法连接后端

- 确认后端服务正在运行
- 检查防火墙是否阻止了连接
- 尝试在浏览器中访问后端地址验证网络连通性

### 托盘图标不显示 (Linux)

- 确保桌面环境支持系统托盘 (如 GNOME 需安装 `gnome-shell-extension-appindicator`)
- 尝试安装 `libappindicator3-1` 包
