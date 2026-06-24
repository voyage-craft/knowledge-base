# 创建自定义插件

> 从零开始开发、测试并打包分发 Knowledge Base 工作流插件

## 概述

本教程将带你完成一个自定义插件的完整开发流程。我们以创建一个 "字数统计" (word_count) 插件为例。

[截图占位]

## 开发流程

### 第一步: 创建插件目录

在 `backend/plugins/third_party/` 下创建插件目录:

```bash
cd backend/plugins/third_party
mkdir word_count
cd word_count
```

目录结构:

```
plugins/third_party/word_count/
  plugin.json       # 插件清单
  processor.py      # 处理器实现
```

### 第二步: 编写 plugin.json

创建 `plugin.json` 清单文件:

```json
{
  "id": "custom.word_count",
  "name": "字数统计",
  "version": "1.0.0",
  "min_system_version": "0.2.0",
  "max_system_version": "1.x",
  "description": "统计文档的字数、字符数、段落数等基本信息",
  "author": "Your Name",
  "category": "process",
  "icon": "BarChart3",
  "color": "bg-sky-500",
  "node_type": "word_count",
  "entry": "processor.py",
  "configurable": true,
  "config_schema": {
    "fields": [
      {
        "type": "select",
        "label": "统计范围",
        "options": ["full", "selection"],
        "default": "full",
        "key": "scope"
      },
      {
        "type": "select",
        "label": "是否包含标点",
        "options": ["yes", "no"],
        "default": "yes",
        "key": "include_punctuation"
      }
    ]
  },
  "dependencies": {
    "python": [">=3.11"]
  },
  "permissions": [],
  "changelog": {
    "1.0.0": "初始版本"
  }
}
```

### 第三步: 实现 processor.py

创建处理器文件:

```python
"""字数统计插件 -- 统计文档的字数、字符数等基本信息。"""

import re
from app.services.workflow.node_registry import NodeProcessor, NodeContext, NodeResult


class WordCountProcessor(NodeProcessor):
    """统计文档字数并生成统计报告。"""

    async def execute(self, context: NodeContext) -> NodeResult:
        text = context.current_text
        if not text:
            return NodeResult(
                output_text="文档内容为空。",
                error="No text to analyze"
            )

        # 获取配置
        config = context.node.get("config", {})
        include_punctuation = config.get("include_punctuation", "yes") == "yes"

        # 统计信息
        stats = self._count_stats(text, include_punctuation)

        # 生成报告
        report = self._generate_report(stats)

        # 将统计结果追加到文档末尾
        output = f"{text}\n\n---\n\n{report}"

        return NodeResult(
            output_text=output,
            output_data={"word_count_stats": stats},
            actions=["统计完成"],
            metadata=stats,
        )

    def _count_stats(self, text: str, include_punctuation: bool) -> dict:
        """统计文本的各项指标。"""
        # 字符数 (含空格)
        char_count = len(text)

        # 字符数 (不含空格)
        char_no_space = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))

        # 中文字符数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))

        # 英文单词数
        english_words = len(re.findall(r'[a-zA-Z]+', text))

        # 段落数
        paragraphs = len([p for p in text.split('\n\n') if p.strip()])

        # 行数
        lines = len(text.split('\n'))

        # 标点符号数
        punctuation_count = len(re.findall(r'[^\w\s]', text))

        # 不含标点的字符数
        if not include_punctuation:
            char_no_space -= punctuation_count

        return {
            "char_count": char_count,
            "char_no_space": char_no_space,
            "chinese_chars": chinese_chars,
            "english_words": english_words,
            "paragraphs": paragraphs,
            "lines": lines,
            "punctuation_count": punctuation_count,
        }

    def _generate_report(self, stats: dict) -> str:
        """生成统计报告文本。"""
        return (
            f"## 文档统计\n\n"
            f"| 指标 | 数值 |\n"
            f"|------|------|\n"
            f"| 总字符数 (含空格) | {stats['char_count']} |\n"
            f"| 总字符数 (不含空格) | {stats['char_no_space']} |\n"
            f"| 中文字符数 | {stats['chinese_chars']} |\n"
            f"| 英文单词数 | {stats['english_words']} |\n"
            f"| 段落数 | {stats['paragraphs']} |\n"
            f"| 行数 | {stats['lines']} |\n"
            f"| 标点符号数 | {stats['punctuation_count']} |\n"
        )
```

---

## 第四步: 测试插件

### 手动测试

在 `backend/` 目录下创建测试脚本:

```python
# test_word_count.py
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.workflow.node_registry import NodeContext

async def test():
    # 导入插件处理器
    from plugins.third_party.word_count.processor import WordCountProcessor

    processor = WordCountProcessor()

    # 创建测试上下文
    context = NodeContext(
        node={"config": {"scope": "full", "include_punctuation": "yes"}},
        document={"id": 1, "title": "测试文档"},
        current_text="这是一段测试文本。\n\nHello world! This is a test document.\n\n它包含中文和英文内容。",
        accumulated_data={},
    )

    # 执行处理器
    result = await processor.execute(context)

    # 打印结果
    print("=== 输出文本 ===")
    print(result.output_text)
    print("\n=== 统计数据 ===")
    print(result.output_data)
    print("\n=== 操作记录 ===")
    print(result.actions)

asyncio.run(test())
```

运行测试:

```bash
cd backend
python test_word_count.py
```

### 使用 pytest 测试

创建 `backend/tests/test_plugin_word_count.py`:

```python
import pytest
from app.services.workflow.node_registry import NodeContext

@pytest.fixture
def processor():
    from plugins.third_party.word_count.processor import WordCountProcessor
    return WordCountProcessor()

@pytest.fixture
def context():
    return NodeContext(
        node={"config": {"scope": "full", "include_punctuation": "yes"}},
        document={"id": 1, "title": "测试文档"},
        current_text="这是测试文本。Hello world!",
        accumulated_data={},
    )

@pytest.mark.asyncio
async def test_word_count_basic(processor, context):
    result = await processor.execute(context)
    assert result.output_text is not None
    assert result.output_data is not None
    assert "word_count_stats" in result.output_data
    stats = result.output_data["word_count_stats"]
    assert stats["char_count"] > 0
    assert stats["chinese_chars"] > 0
    assert stats["english_words"] > 0

@pytest.mark.asyncio
async def test_word_count_empty_text(processor):
    context = NodeContext(
        node={"config": {}},
        document={"id": 1, "title": "空文档"},
        current_text="",
        accumulated_data={},
    )
    result = await processor.execute(context)
    assert result.error is not None
```

运行测试:

```bash
cd backend
pytest tests/test_plugin_word_count.py -v
```

---

## 第五步: 安装插件

### 方式一: 直接加载 (开发时)

将插件放在 `backend/plugins/third_party/` 目录下, 重启后端即可自动加载。

### 方式二: 通过 Web 界面安装

1. 以管理员身份登录
2. 进入 "设置" -> "插件管理"
3. 点击 "上传插件"
4. 选择 `.kbplugin` 文件 (见下方打包说明)

[截图占位]

### 验证加载

检查后端启动日志中是否包含你的插件:

```
INFO: Loaded plugin: custom.word_count v1.0.0
```

---

## 第六步: 打包分发

### 创建 .kbplugin 文件

`.kbplugin` 是一个 ZIP 压缩包, 包含插件目录下的所有文件:

```bash
cd backend/plugins/third_party
cd word_count
zip -r ../word_count.kbplugin . -x "__pycache__/*" "*.pyc"
```

或者使用 Python:

```python
import zipfile
import os

plugin_dir = "backend/plugins/third_party/word_count"
output_file = "word_count.kbplugin"

with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(plugin_dir):
        # 排除缓存文件
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            if file.endswith('.pyc'):
                continue
            file_path = os.path.join(root, file)
            arc_name = os.path.relpath(file_path, plugin_dir)
            zf.write(file_path, arc_name)

print(f"Plugin packaged: {output_file}")
```

### .kbplugin 文件结构

```
word_count.kbplugin (ZIP)
  plugin.json
  processor.py
```

### 分发方式

1. **直接分享**: 将 `.kbplugin` 文件发送给其他用户, 通过 Web 界面上传安装
2. **插件市场**: 提交到 Knowledge Base 插件市场 (如果可用)
3. **版本控制**: 托管在 GitHub 等平台, 提供下载链接

---

## 高级开发技巧

### 使用 LLM 服务

如果你的插件需要调用 LLM:

```python
class MyAIProcessor(NodeProcessor):
    async def execute(self, context: NodeContext) -> NodeResult:
        from app.services.llm_service import llm_service

        text = context.current_text
        prompt = f"请分析以下文本的情感倾向:\n\n{text}"

        result = await llm_service.chat(prompt)
        return NodeResult(output_text=result)
```

记得在 `plugin.json` 中声明 `llm_access` 权限。

### 访问数据库

```python
class MyDBProcessor(NodeProcessor):
    async def execute(self, context: NodeContext) -> NodeResult:
        from sqlalchemy import select
        from app.models.document import Document

        # 使用上下文中的数据库会话
        async with context.db as session:
            result = await session.execute(
                select(Document).where(Document.user_id == context.user_id)
            )
            docs = result.scalars().all()

        return NodeResult(
            output_text=f"共找到 {len(docs)} 篇文档"
        )
```

### 使用累积数据跨节点传递

```python
class MyProcessor(NodeProcessor):
    async def execute(self, context: NodeContext) -> NodeResult:
        # 读取之前节点存储的数据
        prev_data = context.accumulated_data.get("analysis_result", {})

        # 处理逻辑...

        # 存储数据供后续节点使用
        context.accumulated_data["my_result"] = {"key": "value"}

        return NodeResult(output_text=context.current_text)
```

### 条件分支控制

```python
class MyConditionProcessor(NodeProcessor):
    async def execute(self, context: NodeContext) -> NodeResult:
        text = context.current_text

        if len(text) > 1000:
            return NodeResult(
                should_continue=True,
                branch_target="long_text_branch"
            )
        else:
            return NodeResult(
                should_continue=True,
                branch_target="short_text_branch"
            )
```

---

## 调试技巧

### 启用调试日志

在 `backend/.env` 中设置:

```env
DEBUG=true
```

### 添加日志输出

```python
import logging

logger = logging.getLogger(__name__)

class MyProcessor(NodeProcessor):
    async def execute(self, context: NodeContext) -> NodeResult:
        logger.info("Processing document: %s", context.document.get("title"))
        logger.debug("Text length: %d", len(context.current_text))
        # ...
```

### 检查插件是否被加载

```bash
cd backend
python -c "
from app.services.plugin_loader import plugin_loader
plugin_loader.load_all()
for name, info in plugin_loader._loaded.items():
    print(f'{name}: {info.manifest.name} v{info.manifest.version}')
"
```

---

## 检查清单

发布前请确认:

- [ ] `plugin.json` 格式正确且所有必填字段已填写
- [ ] `id` 使用唯一命名 (避免与内置插件冲突)
- [ ] `processor.py` 导出了 `NodeProcessor` 子类
- [ ] 已编写并通过了测试用例
- [ ] 版本号符合 SemVer 格式
- [ ] `min_system_version` 和 `max_system_version` 设置正确
- [ ] 权限声明完整 (不要申请多余权限)
- [ ] 不包含敏感信息 (API Key, 密码等)
- [ ] `.kbplugin` 包不包含缓存文件 (`__pycache__`, `.pyc`)
