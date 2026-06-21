"""Tests for Markdown import and TipTap conversion."""

import pytest
import json
from app.services.content_converter import markdown_to_tiptap, _parse_inline, extract_plain_text


# ── Markdown to TipTap Conversion ───────────────────────────────────────

class TestMarkdownToTiptap:

    def test_simple_paragraph(self):
        md = "Hello world."
        result = markdown_to_tiptap(md)
        assert result["type"] == "doc"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "paragraph"

    def test_heading_h1(self):
        md = "# Title"
        result = markdown_to_tiptap(md)
        assert result["content"][0]["type"] == "heading"
        assert result["content"][0]["attrs"]["level"] == 1

    def test_heading_levels(self):
        for level in range(1, 7):
            md = "#" * level + f" Heading {level}"
            result = markdown_to_tiptap(md)
            assert result["content"][0]["attrs"]["level"] == min(level, 6)

    def test_code_block(self):
        md = "```python\nprint('hello')\n```"
        result = markdown_to_tiptap(md)
        assert result["content"][0]["type"] == "codeBlock"
        assert result["content"][0]["attrs"]["language"] == "python"
        assert result["content"][0]["content"][0]["text"] == "print('hello')"

    def test_code_block_no_language(self):
        md = "```\ncode here\n```"
        result = markdown_to_tiptap(md)
        assert result["content"][0]["type"] == "codeBlock"
        assert result["content"][0]["attrs"] == {}

    def test_bullet_list(self):
        md = "- Item 1\n- Item 2\n- Item 3"
        result = markdown_to_tiptap(md)
        assert result["content"][0]["type"] == "bulletList"
        assert len(result["content"][0]["content"]) == 3

    def test_ordered_list(self):
        md = "1. First\n2. Second\n3. Third"
        result = markdown_to_tiptap(md)
        assert result["content"][0]["type"] == "orderedList"
        assert len(result["content"][0]["content"]) == 3

    def test_blockquote(self):
        md = "> This is a quote"
        result = markdown_to_tiptap(md)
        assert result["content"][0]["type"] == "blockquote"

    def test_horizontal_rule(self):
        md = "---"
        result = markdown_to_tiptap(md)
        assert result["content"][0]["type"] == "horizontalRule"

    def test_empty_document(self):
        md = ""
        result = markdown_to_tiptap(md)
        assert result["type"] == "doc"
        assert result["content"] == []

    def test_mixed_content(self):
        md = "# Title\n\nSome text.\n\n- Item 1\n- Item 2\n\n> Quote\n\n---\n\nEnd."
        result = markdown_to_tiptap(md)
        types = [n["type"] for n in result["content"]]
        assert "heading" in types
        assert "paragraph" in types
        assert "bulletList" in types
        assert "blockquote" in types
        assert "horizontalRule" in types

    def test_multiple_blank_lines(self):
        md = "Para 1\n\n\n\nPara 2"
        result = markdown_to_tiptap(md)
        paragraphs = [n for n in result["content"] if n["type"] == "paragraph"]
        assert len(paragraphs) == 2


# ── Inline Parsing ──────────────────────────────────────────────────────

class TestParseInline:

    def test_plain_text(self):
        nodes = _parse_inline("Hello world")
        assert len(nodes) == 1
        assert nodes[0]["text"] == "Hello world"

    def test_bold(self):
        nodes = _parse_inline("This is **bold** text")
        bold_nodes = [n for n in nodes if n.get("marks") and any(m["type"] == "bold" for m in n["marks"])]
        assert len(bold_nodes) == 1
        assert bold_nodes[0]["text"] == "bold"

    def test_italic(self):
        nodes = _parse_inline("This is *italic* text")
        italic_nodes = [n for n in nodes if n.get("marks") and any(m["type"] == "italic" for m in n["marks"])]
        assert len(italic_nodes) == 1
        assert italic_nodes[0]["text"] == "italic"

    def test_code(self):
        nodes = _parse_inline("Use `code` here")
        code_nodes = [n for n in nodes if n.get("marks") and any(m["type"] == "code" for m in n["marks"])]
        assert len(code_nodes) == 1
        assert code_nodes[0]["text"] == "code"

    def test_link(self):
        nodes = _parse_inline("Visit [Google](https://google.com)")
        link_nodes = [n for n in nodes if n.get("marks") and any(m["type"] == "link" for m in n["marks"])]
        assert len(link_nodes) == 1
        assert link_nodes[0]["text"] == "Google"
        href = link_nodes[0]["marks"][0]["attrs"]["href"]
        assert href == "https://google.com"

    def test_multiple_formats(self):
        nodes = _parse_inline("**bold** and *italic* and `code`")
        assert len(nodes) >= 3

    def test_empty_string(self):
        nodes = _parse_inline("")
        assert len(nodes) >= 1  # Should return at least one node


# ── Plain Text Extraction ───────────────────────────────────────────────

class TestExtractPlainText:

    def test_simple_doc(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "World"}]},
            ],
        }
        result = extract_plain_text(content)
        assert "Hello" in result
        assert "World" in result

    def test_none_input(self):
        assert extract_plain_text(None) == ""

    def test_string_input(self):
        # A plain string that's not valid JSON gets returned as-is
        assert extract_plain_text("not a doc") == "not a doc"

    def test_json_string_input(self):
        # A JSON string that's not a doc type returns empty
        assert extract_plain_text('{"type": "paragraph"}') == ""

    def test_non_doc_type(self):
        assert extract_plain_text({"type": "paragraph", "content": []}) == ""

    def test_nested_content(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": 1}, "content": [
                    {"type": "text", "text": "Title"},
                ]},
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "Body "},
                    {"type": "text", "text": "text"},
                ]},
            ],
        }
        result = extract_plain_text(content)
        assert "Title" in result
        assert "Body" in result
        assert "text" in result


# ── Full Import via API ─────────────────────────────────────────────────

class TestMarkdownImportAPI:

    @pytest.mark.asyncio
    async def test_import_markdown_file(self, async_client):
        await async_client.get("/api/health")
        login = await async_client.post("/api/auth/login", json={
            "username": "admin", "password": "test-admin-password-123",
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        md_content = "# Imported Title\n\nThis is imported content.\n\n- Item 1\n- Item 2"
        resp = await async_client.post(
            "/api/documents/import",
            files={"file": ("test.md", md_content.encode("utf-8"), "text/markdown")},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Imported Title"
        assert data["content_json"]["type"] == "doc"

    @pytest.mark.asyncio
    async def test_import_non_md_rejected(self, async_client):
        await async_client.get("/api/health")
        login = await async_client.post("/api/auth/login", json={
            "username": "admin", "password": "test-admin-password-123",
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = await async_client.post(
            "/api/documents/import",
            files={"file": ("test.txt", b"content", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_import_oversized_file_rejected(self, async_client):
        await async_client.get("/api/health")
        login = await async_client.post("/api/auth/login", json={
            "username": "admin", "password": "test-admin-password-123",
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        resp = await async_client.post(
            "/api/documents/import",
            files={"file": ("large.md", large_content, "text/markdown")},
            headers=headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_import_requires_auth(self, async_client):
        resp = await async_client.post(
            "/api/documents/import",
            files={"file": ("test.md", b"# Title", "text/markdown")},
        )
        assert resp.status_code == 401
