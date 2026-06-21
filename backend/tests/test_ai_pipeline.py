"""Tests for AI pipeline: JSON extraction, document analysis, graph extraction, standardization."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.ai_pipeline import AIPipeline, _extract_json


# ── JSON Extraction Helper ──────────────────────────────────────────────

class TestExtractJson:

    def test_direct_json(self):
        text = '{"title": "Test", "score": 85}'
        result = _extract_json(text)
        assert result == {"title": "Test", "score": 85}

    def test_json_in_code_fence(self):
        text = '```json\n{"title": "Fenced"}\n```'
        result = _extract_json(text)
        assert result == {"title": "Fenced"}

    def test_json_in_code_fence_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_json_embedded_in_text(self):
        text = 'Here is the analysis: {"score": 75} hope it helps.'
        result = _extract_json(text)
        assert result == {"score": 75}

    def test_no_json_found(self):
        assert _extract_json("No JSON here at all.") is None

    def test_malformed_json(self):
        assert _extract_json("{broken json") is None

    def test_empty_string(self):
        assert _extract_json("") is None

    def test_whitespace_only(self):
        assert _extract_json("   ") is None

    def test_nested_json(self):
        text = '{"entities": [{"name": "Python", "type": "technology"}], "score": 90}'
        result = _extract_json(text)
        assert result["score"] == 90
        assert len(result["entities"]) == 1

    def test_json_with_surrounding_chinese_text(self):
        text = '根据分析，结果如下：\n```json\n{"quality_score": 78}\n```\n以上是分析结果。'
        result = _extract_json(text)
        assert result == {"quality_score": 78}


# ── Analyze Document ────────────────────────────────────────────────────

class TestAnalyzeDocument:

    @pytest.mark.asyncio
    async def test_analyze_success(self):
        pipeline = AIPipeline()
        mock_response = '{"title": "AI Doc", "summary": "A test document", "keywords": ["test"], "suggested_tags": ["test"], "suggested_folder": "", "issues": [], "fixes": [], "quality_score": 85}'

        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system prompt"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value=mock_response)
                result = await pipeline.analyze_document("Test content", "test.md")
                assert result["title"] == "AI Doc"
                assert result["quality_score"] == 85
                assert "test" in result["keywords"]

    @pytest.mark.asyncio
    async def test_analyze_parse_failure_returns_fallback(self):
        pipeline = AIPipeline()
        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system prompt"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value="Not valid JSON at all")
                result = await pipeline.analyze_document("Some content", "myfile.md")
                assert result["title"] == "myfile"  # Derived from filename
                assert result["quality_score"] == 50
                assert len(result["issues"]) > 0
                assert result["issues"][0]["type"] == "系统"

    @pytest.mark.asyncio
    async def test_analyze_truncates_long_input(self):
        pipeline = AIPipeline()
        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value='{"title": "T", "summary": "", "keywords": [], "suggested_tags": [], "suggested_folder": "", "issues": [], "fixes": [], "quality_score": 50}')
                long_text = "x" * 20000
                await pipeline.analyze_document(long_text, "long.txt")
                call_args = mock_llm.generate.call_args
                prompt_text = call_args[1]["messages"][0]["content"]
                # The text should be truncated to 8000 chars in the prompt
                assert len(prompt_text) < 20000


# ── Graph Entity Extraction ─────────────────────────────────────────────

class TestExtractGraphEntities:

    @pytest.mark.asyncio
    async def test_extract_success(self):
        pipeline = AIPipeline()
        mock_response = '''{
            "entities": [{"label": "Python", "type": "technology", "description": "Programming language"}],
            "concepts": [{"label": "OOP", "description": "Object-oriented programming"}],
            "relationships": [{"source": "Python", "target": "OOP", "type": "related_to", "description": "supports"}]
        }'''
        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value=mock_response)
                result = await pipeline.extract_graph_entities("Python supports OOP.", "Tech Doc")
                assert len(result["entities"]) == 1
                assert result["entities"][0]["label"] == "Python"
                assert len(result["relationships"]) == 1

    @pytest.mark.asyncio
    async def test_extract_parse_failure_returns_empty(self):
        pipeline = AIPipeline()
        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value="Cannot parse this")
                result = await pipeline.extract_graph_entities("text", "title")
                assert result == {"entities": [], "concepts": [], "relationships": []}

    @pytest.mark.asyncio
    async def test_extract_partial_json_with_defaults(self):
        """If LLM returns partial JSON, missing keys should get defaults."""
        pipeline = AIPipeline()
        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value='{"entities": [{"label": "X", "type": "term", "description": "d"}]}')
                result = await pipeline.extract_graph_entities("text", "title")
                assert len(result["entities"]) == 1
                assert result["concepts"] == []
                assert result["relationships"] == []


# ── Standardize Document ────────────────────────────────────────────────

class TestStandardizeDocument:

    @pytest.mark.asyncio
    async def test_standardize_success(self):
        pipeline = AIPipeline()
        mock_response = '''{
            "structured_summary": "This is a well-structured doc",
            "keywords": ["python", "api"],
            "categories": ["技术"],
            "content_suggestions": {"missing_sections": [], "improvements": ["Add examples"], "structure_score": 80},
            "metadata": {"difficulty": "intermediate", "audience": "developers", "document_type": "教程"}
        }'''
        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value=mock_response)
                result = await pipeline.standardize_document("Content", "Title", ["python"])
                assert result["metadata"]["difficulty"] == "intermediate"
                assert result["content_suggestions"]["structure_score"] == 80

    @pytest.mark.asyncio
    async def test_standardize_failure_returns_fallback(self):
        pipeline = AIPipeline()
        with patch("app.services.ai_pipeline.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.ai_pipeline.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value="Not JSON")
                result = await pipeline.standardize_document("text", "title", [])
                assert result["metadata"]["difficulty"] == "intermediate"
                assert result["content_suggestions"]["structure_score"] == 0
