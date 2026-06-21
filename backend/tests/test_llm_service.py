"""Tests for LLM service: multi-provider support, error handling, config loading."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.llm_service import LLMService


class TestLLMServiceGenerate:
    """Test LLM service generate() method with various providers."""

    @pytest.mark.asyncio
    async def test_generate_no_provider_configured(self):
        """When no API key is set, generate returns an error marker string."""
        svc = LLMService()
        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "openai", "model": "gpt-4", "openai_api_key": "",
            "openai_base_url": "", "anthropic_api_key": "", "anthropic_base_url": "",
            "ollama_base_url": "", "temperature": 0.7,
        }):
            result = await svc.generate(messages=[{"role": "user", "content": "hello"}])
            assert "LLM" in result or "未配置" in result

    @pytest.mark.asyncio
    async def test_generate_unsupported_provider(self):
        svc = LLMService()
        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "unsupported", "model": "x", "openai_api_key": "",
            "openai_base_url": "", "anthropic_api_key": "", "anthropic_base_url": "",
            "ollama_base_url": "", "temperature": 0.7,
        }):
            result = await svc.generate(messages=[{"role": "user", "content": "hello"}])
            assert "不支持" in result or "LLM" in result

    @pytest.mark.asyncio
    async def test_generate_openai_success(self):
        svc = LLMService()
        mock_choice = MagicMock()
        mock_choice.message.content = "Test response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "openai", "model": "gpt-4", "openai_api_key": "sk-test",
            "openai_base_url": "", "anthropic_api_key": "", "anthropic_base_url": "",
            "ollama_base_url": "", "temperature": 0.7,
        }):
            with patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client):
                result = await svc.generate(
                    messages=[{"role": "user", "content": "hello"}],
                    system="You are helpful",
                )
                assert result == "Test response"
                mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_anthropic_success(self):
        svc = LLMService()
        mock_content_block = MagicMock()
        mock_content_block.text = "Anthropic response"
        mock_response = MagicMock()
        mock_response.content = [mock_content_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "anthropic", "model": "claude-3", "openai_api_key": "",
            "openai_base_url": "", "anthropic_api_key": "sk-ant-test",
            "anthropic_base_url": "", "ollama_base_url": "", "temperature": 0.7,
        }):
            with patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client):
                result = await svc.generate(messages=[{"role": "user", "content": "hello"}])
                assert result == "Anthropic response"

    @pytest.mark.asyncio
    async def test_generate_api_exception(self):
        """API errors should be caught and returned as error string, not raised."""
        svc = LLMService()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Rate limit exceeded"))

        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "openai", "model": "gpt-4", "openai_api_key": "sk-test",
            "openai_base_url": "", "anthropic_api_key": "", "anthropic_base_url": "",
            "ollama_base_url": "", "temperature": 0.7,
        }):
            with patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client):
                result = await svc.generate(messages=[{"role": "user", "content": "hello"}])
                assert "错误" in result or "LLM" in result

    @pytest.mark.asyncio
    async def test_generate_ollama_uses_openai_client(self):
        """Ollama provider should use AsyncOpenAI with /v1 base URL."""
        svc = LLMService()
        mock_client = AsyncMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Ollama response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "ollama", "model": "llama3", "openai_api_key": "",
            "openai_base_url": "", "anthropic_api_key": "", "anthropic_base_url": "",
            "ollama_base_url": "http://localhost:11434", "temperature": 0.7,
        }):
            with patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client):
                result = await svc.generate(messages=[{"role": "user", "content": "hello"}])
                assert result == "Ollama response"


class TestLLMServiceStream:
    """Test streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_openai_yields_chunks(self):
        svc = LLMService()

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"

        async def mock_aiter():
            for c in [chunk1, chunk2]:
                yield c

        mock_stream = mock_aiter()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "openai", "model": "gpt-4", "openai_api_key": "sk-test",
            "openai_base_url": "", "anthropic_api_key": "", "anthropic_base_url": "",
            "ollama_base_url": "", "temperature": 0.7,
        }):
            with patch.object(svc, "_get_client", new_callable=AsyncMock, return_value=mock_client):
                tokens = []
                async for token in svc.stream(messages=[{"role": "user", "content": "hi"}]):
                    tokens.append(token)
                assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stream_unconfigured_yields_error(self):
        svc = LLMService()
        with patch.object(svc, "_load_config", new_callable=AsyncMock, return_value={
            "provider": "openai", "model": "gpt-4", "openai_api_key": "",
            "openai_base_url": "", "anthropic_api_key": "", "anthropic_base_url": "",
            "ollama_base_url": "", "temperature": 0.7,
        }):
            tokens = []
            async for token in svc.stream(messages=[{"role": "user", "content": "hi"}]):
                tokens.append(token)
            assert len(tokens) == 1
            assert "未配置" in tokens[0]


class TestLLMServiceClose:

    @pytest.mark.asyncio
    async def test_close_releases_resources(self):
        svc = LLMService()
        mock_client = AsyncMock()
        svc._client = mock_client
        svc._active_provider = "openai"
        await svc.close()
        assert svc._client is None
        assert svc._active_provider is None
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        svc = LLMService()
        await svc.close()  # Should not raise
        assert svc._client is None
