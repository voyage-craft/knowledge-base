"""Tests for prompt registry: defaults, DB override, save, reset."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import asynccontextmanager

from app.services.prompt_registry import (
    PROMPT_DEFAULTS,
    get_prompt,
    get_all_prompts,
)


def _make_mock_session(execute_result=None):
    """Create a properly mocked async context manager and session."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    if execute_result is not None:
        mock_result.scalar_one_or_none.return_value = execute_result
        mock_result.scalars.return_value.all.return_value = (
            execute_result if isinstance(execute_result, list) else []
        )
    else:
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def fake_session_local():
        yield mock_session

    return fake_session_local, mock_session


class TestPromptDefaults:
    """Validate the hardcoded prompt defaults registry."""

    def test_all_prompts_have_required_keys(self):
        for key, meta in PROMPT_DEFAULTS.items():
            assert "label" in meta, f"{key} missing 'label'"
            assert "category" in meta, f"{key} missing 'category'"
            assert "description" in meta, f"{key} missing 'description'"
            assert "default" in meta, f"{key} missing 'default'"
            assert len(meta["default"]) > 0, f"{key} has empty default"

    def test_prompt_keys_follow_naming_convention(self):
        for key in PROMPT_DEFAULTS:
            assert key.startswith("prompt_"), f"Key {key} does not start with 'prompt_'"

    def test_categories_are_valid(self):
        valid_categories = {"chat", "edit", "pipeline", "rag", "workflow"}
        for key, meta in PROMPT_DEFAULTS.items():
            assert meta["category"] in valid_categories, f"{key} has invalid category: {meta['category']}"

    def test_chat_system_prompt_exists(self):
        assert "prompt_chat_system" in PROMPT_DEFAULTS

    def test_edit_prompts_exist(self):
        edit_keys = [
            "prompt_edit_polish", "prompt_edit_expand", "prompt_edit_compress",
            "prompt_edit_translate_zh", "prompt_edit_translate_en", "prompt_edit_fix",
        ]
        for key in edit_keys:
            assert key in PROMPT_DEFAULTS, f"Missing {key}"

    def test_pipeline_prompts_exist(self):
        assert "prompt_pipeline_analyze" in PROMPT_DEFAULTS
        assert "prompt_pipeline_graph_extract" in PROMPT_DEFAULTS
        assert "prompt_pipeline_standardize" in PROMPT_DEFAULTS

    def test_rag_prompts_exist(self):
        assert "prompt_rag_context" in PROMPT_DEFAULTS
        assert "{context}" in PROMPT_DEFAULTS["prompt_rag_context"]["default"]

    def test_workflow_prompts_exist(self):
        assert "prompt_workflow_summarize" in PROMPT_DEFAULTS
        assert "prompt_workflow_keywords" in PROMPT_DEFAULTS


class TestGetPrompt:

    @pytest.mark.asyncio
    async def test_returns_default_when_no_db_override(self):
        fake_ctx, _ = _make_mock_session(execute_result=None)
        with patch("app.core.database.AsyncSessionLocal", fake_ctx):
            result = await get_prompt("prompt_chat_system")
            assert result == PROMPT_DEFAULTS["prompt_chat_system"]["default"]

    @pytest.mark.asyncio
    async def test_returns_db_override_when_set(self):
        mock_setting = MagicMock()
        mock_setting.value = "Custom system prompt from DB"
        fake_ctx, _ = _make_mock_session(execute_result=mock_setting)
        with patch("app.core.database.AsyncSessionLocal", fake_ctx):
            result = await get_prompt("prompt_chat_system")
            assert result == "Custom system prompt from DB"

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_key(self):
        fake_ctx, _ = _make_mock_session(execute_result=None)
        with patch("app.core.database.AsyncSessionLocal", fake_ctx):
            result = await get_prompt("nonexistent_key")
            assert result == ""

    @pytest.mark.asyncio
    async def test_db_error_falls_back_to_default(self):
        """When DB import/creation fails entirely, fall back to hardcoded default."""
        # Patch at the point where the import happens inside get_prompt
        import app.core.database as db_module
        original = db_module.AsyncSessionLocal
        db_module.AsyncSessionLocal = MagicMock(side_effect=Exception("DB down"))
        try:
            result = await get_prompt("prompt_chat_system")
            assert result == PROMPT_DEFAULTS["prompt_chat_system"]["default"]
        finally:
            db_module.AsyncSessionLocal = original


class TestGetAllPrompts:

    @pytest.mark.asyncio
    async def test_returns_all_prompts(self):
        fake_ctx, _ = _make_mock_session(execute_result=None)
        with patch("app.core.database.AsyncSessionLocal", fake_ctx):
            prompts = await get_all_prompts()
            assert len(prompts) == len(PROMPT_DEFAULTS)
            for p in prompts:
                assert "key" in p
                assert "label" in p
                assert "current" in p
                assert "is_modified" in p

    @pytest.mark.asyncio
    async def test_modified_flag_when_db_differs(self):
        mock_setting = MagicMock()
        mock_setting.key = "prompt_chat_system"
        mock_setting.value = "Modified prompt"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_setting]
        mock_session.execute = AsyncMock(return_value=mock_result)

        @asynccontextmanager
        async def fake_session_local():
            yield mock_session

        with patch("app.core.database.AsyncSessionLocal", fake_session_local):
            prompts = await get_all_prompts()
            chat_prompt = next(p for p in prompts if p["key"] == "prompt_chat_system")
            assert chat_prompt["is_modified"] is True
            assert chat_prompt["current"] == "Modified prompt"

    @pytest.mark.asyncio
    async def test_db_error_returns_defaults(self):
        import app.core.database as db_module
        original = db_module.AsyncSessionLocal
        db_module.AsyncSessionLocal = MagicMock(side_effect=Exception("DB down"))
        try:
            prompts = await get_all_prompts()
            assert len(prompts) == len(PROMPT_DEFAULTS)
            for p in prompts:
                assert p["is_modified"] is False
                assert p["current"] == p["default"]
        finally:
            db_module.AsyncSessionLocal = original
