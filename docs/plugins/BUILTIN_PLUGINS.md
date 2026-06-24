# 内置插件参考

> Knowledge Base 22 个内置工作流插件的完整说明

## 概述

Knowledge Base 内置了 22 个工作流插件, 涵盖输入源、文档处理和输出三大类别。这些插件在系统启动时自动加载, 无需手动安装。

[截图占位]

## 插件列表

### 输入类插件 (Input)

| 插件 | ID | 说明 |
|------|-----|------|
| 文档来源 | `kb.builtin.source` | 从知识库中按筛选条件获取文档作为工作流输入源 |

### 处理类插件 (Process)

| 插件 | ID | 说明 |
|------|-----|------|
| AI 润色 | `kb.builtin.polish` | 使用 AI 对文档内容进行智能润色和优化 |
| AI 深度分析 | `kb.builtin.ai_analyze` | 使用 AI 对文档进行深度分析, 提取目录、结构和质量评估 |
| 生成摘要 | `kb.builtin.summarize` | 使用 AI 为文档生成不同格式的内容摘要 |
| 精简压缩 | `kb.builtin.compress` | 使用 AI 对文档内容进行精简压缩, 保留核心要点 |
| 内容扩展 | `kb.builtin.expand` | 使用 AI 对文档内容进行扩展和丰富 |
| 修正语法 | `kb.builtin.fix` | 使用 AI 修正文档中的语法、拼写和样式错误 |
| 翻译为中文 | `kb.builtin.translate_zh` | 使用 AI 将文档内容翻译为中文 |
| 翻译为英文 | `kb.builtin.translate_en` | 使用 AI 将文档内容翻译为英文 |
| 提取关键词 | `kb.builtin.keywords` | 使用 AI 从文档内容中提取关键词和短语 |
| 智能重命名 | `kb.builtin.rename` | 使用 AI 根据文档内容智能生成更合适的标题 |
| 标准化分析 | `kb.builtin.standardize` | 使用 AI 对文档进行标准化分析并提取结构化信息 |
| 自动打标签 | `kb.builtin.auto_tag` | 根据文档内容自动分析并添加合适的标签 |
| 自定义提示词 | `kb.builtin.custom_prompt` | 使用用户自定义的提示词对文档内容进行处理 |
| 格式转换 | `kb.builtin.format_convert` | 将文档内容在不同格式之间进行转换 |
| 生成嵌入 | `kb.builtin.embedding` | 为文档内容生成向量嵌入以支持语义搜索 |
| 设置元数据 | `kb.builtin.set_metadata` | 批量设置文档的状态和标签等元数据信息 |
| 人工审批 | `kb.builtin.approval` | 在工作流中插入人工审批节点, 等待审核通过后继续执行 |
| 条件分支 | `kb.builtin.condition` | 根据条件判断结果将工作流引导至不同的分支路径 |
| 循环处理 | `kb.builtin.loop` | 对集合中的每个元素重复执行后续工作流节点 |

### 输出类插件 (Output)

| 插件 | ID | 说明 |
|------|-----|------|
| 保存文档 | `kb.builtin.save` | 将工作流处理后的文档内容保存回知识库 |
| 导出文档 | `kb.builtin.export` | 将文档导出为多种格式的文件以供外部使用 |

---

## 详细说明

### 文档来源 (kb.builtin.source)

从知识库中获取文档作为工作流的输入源。

| 属性 | 值 |
|------|-----|
| 分类 | input |
| 图标 | FolderOpen |
| 颜色 | bg-emerald-500 |
| 权限 | database_read |

**配置项**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| 筛选条件 | select | 按什么条件筛选文档 | `all` |
| 排序方式 | select (高级) | 文档排序方式 | `date` |
| 数量限制 | text (高级) | 最大返回文档数量 | 不限制 |

筛选条件选项: `all` (全部), `folder` (按文件夹), `tag` (按标签), `status` (按状态)

---

### AI 润色 (kb.builtin.polish)

使用 AI 对文档内容进行智能润色, 提升文章质量和可读性。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Sparkles |
| 颜色 | bg-blue-500 |
| 权限 | llm_access |

**配置项**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| 润色强度 | select | 润色程度 | `medium` |
| 保持风格 | select | 是否保持原文风格 | `true` |
| 自定义指令 | textarea (高级) | 额外的润色指令 | 空 |

---

### AI 深度分析 (kb.builtin.ai_analyze)

对文档进行深度分析, 提取目录结构、内容质量评估等结构化信息。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Search |
| 颜色 | bg-fuchsia-500 |
| 权限 | llm_access |

---

### 生成摘要 (kb.builtin.summarize)

使用 AI 为文档生成摘要, 支持不同长度和格式。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | FileText |
| 颜色 | bg-teal-500 |
| 权限 | llm_access |

**配置项**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| 摘要长度 | select | short / medium / long | `medium` |
| 输出格式 | select | paragraph / bullets / structured | `paragraph` |
| 自定义提示词 | textarea (高级) | 自定义摘要指令 | 空 |

---

### 精简压缩 (kb.builtin.compress)

使用 AI 精简文档内容, 去除冗余信息, 保留核心要点。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Minimize2 |
| 颜色 | bg-purple-500 |
| 权限 | llm_access |

---

### 内容扩展 (kb.builtin.expand)

使用 AI 对文档内容进行扩展, 丰富细节和论述。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Expand |
| 颜色 | bg-indigo-500 |
| 权限 | llm_access |

---

### 修正语法 (kb.builtin.fix)

使用 AI 修正文档中的语法、拼写和标点错误。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Wrench |
| 颜色 | bg-amber-500 |
| 权限 | llm_access |

---

### 翻译为中文 (kb.builtin.translate_zh)

使用 AI 将文档内容翻译为中文, 支持不同正式程度和专业领域。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Languages |
| 颜色 | bg-pink-500 |
| 权限 | llm_access |

**配置项**:

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| 正式程度 | select | formal / neutral / informal | `neutral` |
| 领域 | select | general / technical / legal / medical | `general` |
| 自定义术语表 | textarea (高级) | 每行: 原文=译文 | 空 |

---

### 翻译为英文 (kb.builtin.translate_en)

使用 AI 将文档内容翻译为英文。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Languages |
| 颜色 | bg-rose-500 |
| 权限 | llm_access |

---

### 提取关键词 (kb.builtin.keywords)

使用 AI 从文档中提取关键术语和短语。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Key |
| 颜色 | bg-cyan-500 |
| 权限 | llm_access |

---

### 智能重命名 (kb.builtin.rename)

使用 AI 分析文档内容, 生成更准确、更有吸引力的标题。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Sparkles |
| 颜色 | bg-emerald-600 |
| 权限 | llm_access |

---

### 标准化分析 (kb.builtin.standardize)

对文档进行标准化分析, 提取结构化信息 (如分类、关键词、质量评分)。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | ClipboardCheck |
| 颜色 | bg-violet-500 |
| 权限 | llm_access |

---

### 自动打标签 (kb.builtin.auto_tag)

根据文档内容自动分析并添加合适的标签。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Tags |
| 颜色 | bg-orange-500 |
| 权限 | llm_access |

---

### 自定义提示词 (kb.builtin.custom_prompt)

允许用户编写自定义提示词来处理文档内容, 灵活度最高。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | MessageSquare |
| 颜色 | bg-slate-500 |
| 权限 | llm_access |

---

### 格式转换 (kb.builtin.format_convert)

在不同文档格式之间进行转换 (如 Markdown -> HTML, 纯文本 -> Markdown)。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | FileText |
| 颜色 | bg-lime-500 |

---

### 生成嵌入 (kb.builtin.embedding)

为文档内容生成向量嵌入, 用于支持语义搜索功能。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Sparkles |
| 颜色 | bg-teal-600 |

---

### 设置元数据 (kb.builtin.set_metadata)

批量设置文档的元数据信息, 如状态、标签等。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Tags |
| 颜色 | bg-blue-600 |
| 权限 | database_write |

---

### 人工审批 (kb.builtin.approval)

在工作流中插入审批节点, 暂停执行等待人工审核。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | ClipboardCheck |
| 颜色 | bg-red-500 |

---

### 条件分支 (kb.builtin.condition)

根据条件判断将工作流引导至不同分支, 实现逻辑分流。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Sparkles |
| 颜色 | bg-yellow-500 |

---

### 循环处理 (kb.builtin.loop)

对集合中的每个元素重复执行后续节点, 实现批量处理。

| 属性 | 值 |
|------|-----|
| 分类 | process |
| 图标 | Sparkles |
| 颜色 | bg-sky-500 |

---

### 保存文档 (kb.builtin.save)

将工作流处理后的结果保存回知识库。

| 属性 | 值 |
|------|-----|
| 分类 | output |
| 图标 | Save |
| 颜色 | bg-green-500 |
| 权限 | database_write |

---

### 导出文档 (kb.builtin.export)

将文档导出为外部文件格式。

| 属性 | 值 |
|------|-----|
| 分类 | output |
| 图标 | FileText |
| 颜色 | bg-amber-600 |
| 权限 | file_write |

---

## 示例工作流

### 工作流 1: 批量翻译

```
文档来源 (所有英文文档) -> 翻译为中文 -> 保存文档
```

### 工作流 2: 内容审核

```
文档来源 (待审核文档) -> AI 深度分析 -> 人工审批 -> 保存文档
```

### 工作流 3: 文档标准化

```
文档来源 (指定文件夹) -> 修正语法 -> 标准化分析 -> 自动打标签 -> 保存文档
```

### 工作流 4: 批量摘要生成

```
文档来源 (长文档) -> 生成摘要 (medium, bullets) -> 保存文档
```

### 工作流 5: 内容润色与发布

```
文档来源 (草稿) -> AI 润色 -> 智能重命名 -> 人工审批 -> 保存文档 (发布状态)
```

### 工作流 6: 多语言处理

```
文档来源 -> 条件分支 (语言检测)
  -> 中文: 翻译为英文 -> 保存
  -> 英文: 翻译为中文 -> 保存
```
