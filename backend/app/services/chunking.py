"""Document chunking service for RAG.

Splits document text into overlapping chunks suitable for embedding.
Uses character-based heuristics (no external tokenizer needed).
"""

import logging

logger = logging.getLogger(__name__)

# Approximate chars-per-token: ~1.5 for Chinese, ~4 for English.
# We use a conservative 3.0 for mixed content.
CHARS_PER_TOKEN = 3.0

DEFAULT_CHUNK_SIZE = 500     # tokens per chunk
DEFAULT_OVERLAP = 50         # tokens of overlap between chunks


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate for mixed CJK/English text."""
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict]:
    """Split text into overlapping chunks.

    Strategy:
    1. Split by double-newline (paragraphs) first
    2. If a paragraph exceeds chunk_size, split by single-newline
    3. If still too large, split by sentences, then by words
    4. Merge small consecutive chunks up to chunk_size
    5. Add overlap from the end of each chunk to the start of the next

    Returns list of {chunk_index, chunk_text}.
    """
    if not text or not text.strip():
        return []

    target_chars = int(chunk_size * CHARS_PER_TOKEN)
    overlap_chars = int(overlap * CHARS_PER_TOKEN)

    # Step 1: Split into raw segments
    raw_segments = _split_recursive(text, target_chars)

    # Step 2: Merge small segments up to target
    merged = _merge_segments(raw_segments, target_chars)

    # Step 3: Add overlap
    chunks: list[dict] = []
    for i, seg in enumerate(merged):
        chunk_text_val = seg
        # Prepend overlap from previous chunk
        if i > 0 and overlap_chars > 0:
            prev = merged[i - 1]
            overlap_text = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
            chunk_text_val = overlap_text + "\n" + chunk_text_val
        chunks.append({
            "chunk_index": i,
            "chunk_text": chunk_text_val.strip(),
        })

    logger.debug("Chunked %d chars into %d chunks", len(text), len(chunks))
    return chunks


def _split_recursive(text: str, max_chars: int) -> list[str]:
    """Recursively split text by separators until chunks are under max_chars."""
    if len(text) <= max_chars:
        return [text.strip()] if text.strip() else []

    # Try splitting by paragraph breaks
    if "\n\n" in text:
        parts = text.split("\n\n")
        result = []
        for part in parts:
            if len(part) > max_chars:
                result.extend(_split_recursive(part, max_chars))
            elif part.strip():
                result.append(part.strip())
        return result

    # Try splitting by single newlines
    if "\n" in text:
        parts = text.split("\n")
        result = []
        for part in parts:
            if len(part) > max_chars:
                result.extend(_split_further(part, max_chars))
            elif part.strip():
                result.append(part.strip())
        return result

    # Fall back to sentence/word splitting
    return _split_further(text, max_chars)


def _split_further(text: str, max_chars: int) -> list[str]:
    """Split text that has no newline breaks — use sentence or character splitting."""
    # Try splitting by sentence-ending punctuation
    import re
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    if len(sentences) > 1:
        result = []
        for s in sentences:
            if len(s) > max_chars:
                # Character-level split as last resort
                for start in range(0, len(s), max_chars):
                    chunk = s[start:start + max_chars].strip()
                    if chunk:
                        result.append(chunk)
            elif s.strip():
                result.append(s.strip())
        return result

    # Character-level split
    result = []
    for start in range(0, len(text), max_chars):
        chunk = text[start:start + max_chars].strip()
        if chunk:
            result.append(chunk)
    return result


def _merge_segments(segments: list[str], max_chars: int) -> list[str]:
    """Merge consecutive small segments up to max_chars."""
    if not segments:
        return []

    merged: list[str] = []
    current = segments[0]

    for seg in segments[1:]:
        combined = current + "\n\n" + seg
        if len(combined) <= max_chars:
            current = combined
        else:
            merged.append(current)
            current = seg

    merged.append(current)
    return merged
