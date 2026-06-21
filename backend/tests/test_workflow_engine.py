"""Tests for workflow engine: topological sort, TipTap stripping, node processors, and full execution."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.workflow_engine import (
    _topo_sort,
    _strip_tiptap,
    _process_keywords,
)


# ── Topological Sort ────────────────────────────────────────────────────

class TestTopoSort:
    """Unit tests for Kahn's algorithm topological sort."""

    def test_linear_chain(self):
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
        order = _topo_sort(nodes, edges)
        assert order.index("a") < order.index("b") < order.index("c")

    def test_diamond_graph(self):
        """A -> B, A -> C, B -> D, C -> D"""
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
            {"source": "b", "target": "d"},
            {"source": "c", "target": "d"},
        ]
        order = _topo_sort(nodes, edges)
        assert order[0] == "a"
        assert order[-1] == "d"
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_single_node(self):
        nodes = [{"id": "x"}]
        edges = []
        assert _topo_sort(nodes, edges) == ["x"]

    def test_empty_graph(self):
        assert _topo_sort([], []) == []

    def test_disconnected_nodes(self):
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = []
        order = _topo_sort(nodes, edges)
        assert set(order) == {"a", "b", "c"}

    def test_multiple_roots(self):
        """Two independent chains: a->b, c->d."""
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]
        edges = [{"source": "a", "target": "b"}, {"source": "c", "target": "d"}]
        order = _topo_sort(nodes, edges)
        assert order.index("a") < order.index("b")
        assert order.index("c") < order.index("d")

    def test_complex_workflow_graph(self):
        """Simulate the SUMMARIZE_TAG template: source -> summarize, source -> keywords, summarize -> auto_tag, keywords -> auto_tag, auto_tag -> save."""
        nodes = [
            {"id": "source"}, {"id": "summarize"}, {"id": "keywords"},
            {"id": "auto_tag"}, {"id": "save"},
        ]
        edges = [
            {"source": "source", "target": "summarize"},
            {"source": "source", "target": "keywords"},
            {"source": "summarize", "target": "auto_tag"},
            {"source": "keywords", "target": "auto_tag"},
            {"source": "auto_tag", "target": "save"},
        ]
        order = _topo_sort(nodes, edges)
        assert order[0] == "source"
        assert order[-1] == "save"
        assert order.index("summarize") < order.index("auto_tag")
        assert order.index("keywords") < order.index("auto_tag")


# ── TipTap Stripping ────────────────────────────────────────────────────

class TestStripTiptap:
    """Unit tests for plain text extraction from TipTap JSON."""

    def test_simple_paragraph(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}
            ],
        }
        assert _strip_tiptap(content) == "Hello world"

    def test_multiple_paragraphs(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "First"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Second"}]},
            ],
        }
        result = _strip_tiptap(content)
        assert "First" in result
        assert "Second" in result

    def test_string_input(self):
        assert _strip_tiptap("just a string") == "just a string"

    def test_json_string_input(self):
        import json
        content = json.dumps({
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Parsed"}]}],
        })
        assert "Parsed" in _strip_tiptap(content)

    def test_none_input(self):
        assert _strip_tiptap(None) == "None"

    def test_empty_doc(self):
        assert _strip_tiptap({"type": "doc", "content": []}) == ""

    def test_integer_input(self):
        assert _strip_tiptap(42) == "42"

    def test_invalid_json_string(self):
        assert _strip_tiptap("{not json") == "{not json"


# ── Keywords Extraction ─────────────────────────────────────────────────

class TestProcessKeywords:
    """Test keyword extraction from LLM responses."""

    @pytest.mark.asyncio
    async def test_extract_json_array(self):
        with patch("app.services.workflow_engine.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.workflow_engine.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value='["python", "fastapi", "testing"]')
                result = await _process_keywords("Some document text about Python and FastAPI")
                assert result == ["python", "fastapi", "testing"]

    @pytest.mark.asyncio
    async def test_no_json_in_response(self):
        with patch("app.services.workflow_engine.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.workflow_engine.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value="I cannot extract keywords.")
                result = await _process_keywords("Some text")
                assert result == []

    @pytest.mark.asyncio
    async def test_json_embedded_in_text(self):
        with patch("app.services.workflow_engine.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.workflow_engine.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value='Here are the keywords: ["ai", "ml"] hope this helps.')
                result = await _process_keywords("Text about AI and ML")
                assert result == ["ai", "ml"]

    @pytest.mark.asyncio
    async def test_malformed_json_array(self):
        with patch("app.services.workflow_engine.get_prompt", new_callable=AsyncMock, return_value="system"):
            with patch("app.services.workflow_engine.llm_service") as mock_llm:
                mock_llm.generate = AsyncMock(return_value='["unclosed, array')
                result = await _process_keywords("Text")
                assert result == []
