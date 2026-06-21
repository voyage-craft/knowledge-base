"""Tests for the document chunking service (RAG)."""

import pytest
from app.services.chunking import chunk_text, _estimate_tokens, _split_recursive, _merge_segments, CHARS_PER_TOKEN


# ── Token Estimation ────────────────────────────────────────────────────

class TestEstimateTokens:

    def test_empty_string(self):
        assert _estimate_tokens("") == 1  # max(1, 0)

    def test_short_text(self):
        # 3 chars / 3.0 = 1 token
        assert _estimate_tokens("abc") == 1

    def test_long_text(self):
        text = "a" * 300
        assert _estimate_tokens(text) == 100


# ── Chunk Text ──────────────────────────────────────────────────────────

class TestChunkText:

    def test_empty_text(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        text = "Hello world. This is a short document."
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0]["chunk_index"] == 0
        assert "Hello world" in chunks[0]["chunk_text"]

    def test_paragraph_splitting(self):
        para1 = "A" * 1000
        para2 = "B" * 1000
        text = f"{para1}\n\n{para2}"
        # chunk_size=100 tokens => ~300 chars target
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) >= 2
        # All chunks should have sequential indices
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i

    def test_overlap_present(self):
        """Verify that chunks after the first contain overlap text from previous chunk."""
        text = "First section content.\n\nSecond section content.\n\nThird section content."
        chunks = chunk_text(text, chunk_size=20, overlap=5)
        if len(chunks) > 1:
            # Second chunk should contain some text from first chunk's end
            assert len(chunks[1]["chunk_text"]) > len("Second section content.")

    def test_single_long_line(self):
        """A single line longer than chunk_size gets split by character."""
        text = "x" * 5000
        chunks = chunk_text(text, chunk_size=50, overlap=5)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c["chunk_text"]) > 0

    def test_chunk_indices_sequential(self):
        text = "\n\n".join([f"Paragraph {i} with some content here." for i in range(20)])
        chunks = chunk_text(text, chunk_size=30, overlap=5)
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i

    def test_no_empty_chunks(self):
        text = "\n\n\n\nLots\n\nof\n\nempty\n\nlines\n\n"
        chunks = chunk_text(text, chunk_size=50, overlap=5)
        for c in chunks:
            assert c["chunk_text"].strip() != ""

    def test_mixed_language_text(self):
        text = "This is English text. 这是中文文本。More English here. 更多中文。"
        chunks = chunk_text(text, chunk_size=10, overlap=2)
        assert len(chunks) >= 1
        full_reconstructed = " ".join(c["chunk_text"] for c in chunks)
        # Key content should survive chunking
        assert "English" in full_reconstructed or "中文" in full_reconstructed

    def test_default_parameters(self):
        """Verify default chunk_size and overlap produce reasonable results."""
        text = "word " * 1000  # ~5000 chars
        chunks = chunk_text(text)
        assert len(chunks) > 1
        for c in chunks:
            assert "chunk_index" in c
            assert "chunk_text" in c


# ── Recursive Split ─────────────────────────────────────────────────────

class TestSplitRecursive:

    def test_text_under_limit(self):
        result = _split_recursive("short text", max_chars=1000)
        assert result == ["short text"]

    def test_split_by_paragraph(self):
        text = "para one\n\npara two\n\npara three"
        result = _split_recursive(text, max_chars=20)
        assert len(result) >= 3

    def test_split_by_newline(self):
        text = "line one\nline two\nline three"
        result = _split_recursive(text, max_chars=15)
        assert len(result) >= 3


# ── Merge Segments ──────────────────────────────────────────────────────

class TestMergeSegments:

    def test_empty_segments(self):
        assert _merge_segments([], 100) == []

    def test_single_segment(self):
        assert _merge_segments(["hello"], 100) == ["hello"]

    def test_merge_small_segments(self):
        segments = ["a", "b", "c"]
        result = _merge_segments(segments, max_chars=100)
        assert len(result) == 1
        assert "a" in result[0] and "b" in result[0] and "c" in result[0]

    def test_no_merge_when_over_limit(self):
        segments = ["a" * 100, "b" * 100]
        result = _merge_segments(segments, max_chars=50)
        assert len(result) == 2
