# 插件规范

> Knowledge Base 插件开发规范 -- plugin.json 清单格式与开发要求

## 插件系统概述

Knowledge Base 使用插件系统来管理工作流中的节点处理器。每个插件是一个独立的目录, 包含:

- `plugin.json` -- 插件清单文件 (必须)
- `processor.py` -- 处理器实现文件 (默认入口)

```
plugins/
  builtin/                    # 内置插件 (随系统发布)
    kb.builtin.summarize/
      plugin.json
      processor.py
  third_party/                # 第三方插件 (用户安装)
    my-custom-plugin/
      plugin.json
      processor.py
```

---

## plugin.json 清单格式

`plugin.json` 是插件的核心描述文件, 定义了插件的元数据、配置和兼容性信息。

### 完整 Schema

```json
{
  "id": "kb.builtin.summarize",
  "name": "生成摘要",
  "version": "1.1.0",
  "min_system_version": "0.2.0",
  "max_system_version": "1.x",
  "description": "使用 AI 为文档生成不同格式的内容摘要",
  "author": "Knowledge Base Team",
  "category": "process",
  "icon": "FileText",
  "color": "bg-teal-500",
  "node_type": "summarize",
  "entry": "processor.py",
  "configurable": true,
  "config_schema": {
    "fields": [
      {
        "type": "select",
        "label": "摘要长度",
        "options": ["short", "medium", "long"],
        "default": "medium",
        "key": "summary_length"
      }
    ]
  },
  "dependencies": {
    "python": [">=3.11"]
  },
  "permissions": ["llm_access"],
  "changelog": {
    "1.0.0": "初始版本",
    "1.1.0": "新增结构化输出格式"
  },
  "plugin_api_version": "1.0",
  "manifest_version": 1
}
```

### 字段详细说明

#### 基础字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 插件唯一标识符, 格式: `命名空间.插件名` |
| `name` | string | 是 | 插件显示名称 (中文) |
| `version` | string | 是 | 插件版本号 (SemVer 格式) |
| `description` | string | 否 | 插件功能描述 |
| `author` | string | 否 | 作者名称 |

#### 分类与外观

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `category` | string | 否 | 分类: `input`, `process`, `output` (默认 `process`) |
| `icon` | string | 否 | 图标名称 (Lucide React 图标名, 默认 `Sparkles`) |
| `color` | string | 否 | 颜色类名 (Tailwind CSS 类, 默认 `bg-blue-500`) |

#### 节点配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `node_type` | string | 是 | 节点类型标识, 用于工作流引擎匹配 |
| `entry` | string | 否 | 入口文件名 (默认 `processor.py`) |
| `configurable` | bool | 否 | 是否支持用户配置 (默认 `false`) |

#### 版本兼容性

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `min_system_version` | string | 否 | 最低系统版本 (默认 `0.0.0`) |
| `max_system_version` | string | 否 | 最高系统版本, 支持 `x` 通配符 (默认 `99.x`) |
| `plugin_api_version` | string | 否 | 插件 API 版本 (默认 `1.0`) |
| `manifest_version` | int | 否 | 清单格式版本 (默认 `1`) |

#### 依赖与权限

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `dependencies` | object | 否 | 依赖声明 |
| `permissions` | array | 否 | 所需权限列表 |
| `changelog` | object | 否 | 版本变更日志 |

---

## category 类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `input` | 输入节点, 提供数据源 | 文档来源 |
| `process` | 处理节点, 对数据进行转换 | 摘要, 翻译, 润色 |
| `output` | 输出节点, 将结果写入外部 | 保存文档, 导出文件 |

---

## ConfigField 配置字段类型

当 `configurable` 为 `true` 时, `config_schema.fields` 定义用户可配置的选项:

### text -- 文本输入

```json
{
  "type": "text",
  "label": "数量限制",
  "placeholder": "不限制",
  "key": "limit",
  "default": "",
  "advanced": false
}
```

### select -- 下拉选择

```json
{
  "type": "select",
  "label": "摘要长度",
  "options": ["short", "medium", "long"],
  "default": "medium",
  "key": "summary_length"
}
```

### textarea -- 多行文本

```json
{
  "type": "textarea",
  "label": "自定义提示词",
  "placeholder": "请输入自定义提示词...",
  "key": "custom_prompt",
  "advanced": true
}
```

### number -- 数字输入

```json
{
  "type": "number",
  "label": "最大长度",
  "default": "500",
  "key": "max_length"
}
```

### ConfigField 字段属性

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | 字段键名 (在代码中引用) |
| `label` | string | 是 | 显示标签 |
| `type` | string | 否 | 字段类型: `text`, `select`, `textarea`, `number` |
| `options` | array | 否 | 选项列表 (仅 `select` 类型) |
| `default` | string | 否 | 默认值 |
| `placeholder` | string | 否 | 占位提示文本 |
| `advanced` | bool | 否 | 是否在"高级"区域显示 (默认 `false`) |

---

## 权限系统

插件可以声明所需权限:

| 权限 | 说明 |
|------|------|
| `llm_access` | 访问 LLM 服务 (AI 分析、摘要等) |
| `database_read` | 读取数据库 |
| `database_write` | 写入数据库 |
| `file_read` | 读取文件 |
| `file_write` | 写入文件 |
| `network` | 网络访问 |

---

## 入口文件要求

入口文件 (默认 `processor.py`) 必须导出一个继承自 `NodeProcessor` 的类。

### NodeProcessor 基类

```python
from app.services.workflow.node_registry import NodeProcessor, NodeContext, NodeResult

class NodeProcessor:
    async def execute(self, context: NodeContext) -> NodeResult:
        """执行节点逻辑。必须实现此方法。"""
        raise NotImplementedError

    def get_prompt_key(self) -> Optional[str]:
        """返回提示词键名 (LLM 节点使用)。"""
        return None
```

### NodeContext -- 执行上下文

```python
@dataclass
class NodeContext:
    node: dict              # 当前节点配置
    document: dict          # {id, title, text, content_json}
    current_text: str       # 当前处理的文本
    accumulated_data: dict  # 跨节点共享状态
    db: AsyncSession        # 数据库会话
    user_id: int            # 当前用户 ID
    run_id: int             # 工作流运行 ID
    extra: dict             # 额外上下文数据
```

### NodeResult -- 执行结果

```python
@dataclass
class NodeResult:
    output_text: str        # 修改后的文本 (编辑类节点)
    output_data: dict       # 结构化数据 (分析类节点)
    should_continue: bool   # 是否继续执行 (条件节点)
    branch_target: str      # 分支目标 (分支节点)
    error: str              # 错误信息
    actions: list[str]      # 执行的操作列表
    metadata: dict          # 附加元数据
```

### 最小实现示例

```python
# processor.py
from app.services.workflow.node_registry import NodeProcessor, NodeContext, NodeResult

class MyProcessor(NodeProcessor):
    async def execute(self, context: NodeContext) -> NodeResult:
        text = context.current_text
        # 你的处理逻辑
        processed = text.upper()
        return NodeResult(output_text=processed)
```

---

## SemVer 版本要求

版本号遵循 [语义化版本](https://semver.org/) 规范:

| 格式 | 说明 | 示例 |
|------|------|------|
| `MAJOR.MINOR.PATCH` | 标准版本 | `1.2.3` |
| `1.x` | 通配符, 匹配所有 1.y 版本 | max_system_version |

### 系统版本兼容性检查

系统通过 `version_matches()` 函数检查插件兼容性:

```python
# 检查当前系统版本是否在 [min, max] 范围内
version_matches(
    current="0.2.0",
    min_ver="0.2.0",   # 最低版本
    max_ver="1.x"      # 最高版本 (含通配符)
)
# 返回 True
```

当前系统版本: **0.2.0** | 插件 API 版本: **1.0**
