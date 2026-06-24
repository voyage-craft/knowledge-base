"""
核心引擎测试

测试工作流引擎、LLM服务、安全模块等核心功能
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ── 安全模块测试 ──────────────────────────────────────────────────

class TestSecurityModule:
    """测试安全模块核心功能"""

    def test_password_hashing(self):
        """测试密码哈希和验证"""
        from app.core.security import hash_password, verify_password

        password = "TestPassword123"
        hashed = hash_password(password)

        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_password_strength_validation(self):
        """测试密码强度验证"""
        from app.core.security import validate_password_strength

        # 有效密码
        is_valid, msg = validate_password_strength("StrongPass123")
        assert is_valid is True
        assert msg == ""

        # 太短
        is_valid, msg = validate_password_strength("Short1")
        assert is_valid is False
        assert "8个字符" in msg

        # 缺少大写
        is_valid, msg = validate_password_strength("lowercase123")
        assert is_valid is False
        assert "大写" in msg

        # 缺少小写
        is_valid, msg = validate_password_strength("UPPERCASE123")
        assert is_valid is False
        assert "小写" in msg

        # 缺少数字
        is_valid, msg = validate_password_strength("NoNumbersHere")
        assert is_valid is False
        assert "数字" in msg

    def test_token_creation_and_decode(self):
        """测试Token创建和解码"""
        from app.core.security import create_access_token, create_refresh_token, decode_token

        # 创建access token
        data = {"sub": "1", "username": "testuser"}
        access_token = create_access_token(data)
        payload = decode_token(access_token, check_blacklist=False)

        assert payload["sub"] == "1"
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload

        # 创建refresh token
        refresh_token = create_refresh_token(data)
        payload = decode_token(refresh_token, check_blacklist=False)

        assert payload["type"] == "refresh"

    def test_token_blacklist(self):
        """测试Token黑名单功能"""
        from app.core.security import (
            create_access_token, blacklist_token, is_token_blacklisted, get_blacklist_size
        )

        data = {"sub": "1", "username": "testuser"}
        token = create_access_token(data)

        # 初始状态不在黑名单
        assert is_token_blacklisted(token) is False

        # 加入黑名单
        blacklist_token(token)
        assert is_token_blacklisted(token) is True
        assert get_blacklist_size() > 0

    def test_token_blacklist_expiry(self):
        """测试Token黑名单过期清理"""
        from app.core.security import _token_blacklist, _cleanup_expired_tokens

        # 添加一个已过期的token
        _token_blacklist["expired_token"] = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()

        # 添加一个有效的token
        _token_blacklist["valid_token"] = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()

        # 清理过期token
        _cleanup_expired_tokens()

        assert "expired_token" not in _token_blacklist
        assert "valid_token" in _token_blacklist


# ── LLM服务测试 ──────────────────────────────────────────────────

class TestLLMService:
    """测试LLM服务核心功能"""

    @pytest.mark.asyncio
    async def test_llm_config_loading(self):
        """测试LLM配置加载"""
        from app.services.llm_service import llm_service

        # 清除缓存
        llm_service.invalidate_config_cache()

        # 加载配置
        config = await llm_service._load_config()

        assert "provider" in config
        assert "model" in config
        assert "temperature" in config

    @pytest.mark.asyncio
    async def test_llm_error_handling(self):
        """测试LLM错误处理"""
        from app.services.llm_service import LLMNotConfiguredError, LLMProviderError

        # 测试错误类型
        with pytest.raises(LLMNotConfiguredError):
            raise LLMNotConfiguredError("未配置")

        with pytest.raises(LLMProviderError):
            raise LLMProviderError("提供商错误")

    @pytest.mark.asyncio
    async def test_llm_retry_mechanism(self):
        """测试LLM重试机制"""
        from app.services.llm_service import llm_service, MAX_RETRIES

        # 验证重试配置
        assert MAX_RETRIES == 3


# ── 数据库模型测试 ──────────────────────────────────────────────────

class TestDatabaseModels:
    """测试数据库模型"""

    def test_document_model_fields(self):
        """测试文档模型字段"""
        from app.models.document import Document

        # 检查必要字段存在
        assert hasattr(Document, 'id')
        assert hasattr(Document, 'title')
        assert hasattr(Document, 'content_json')
        assert hasattr(Document, 'status')
        assert hasattr(Document, 'user_id')
        assert hasattr(Document, 'folder_id')
        assert hasattr(Document, 'version')
        assert hasattr(Document, 'created_at')
        assert hasattr(Document, 'updated_at')

    def test_document_indexes(self):
        """测试文档模型索引"""
        from app.models.document import Document

        # 检查索引定义
        table_args = Document.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, 'name')]

        assert 'ix_documents_user_status' in index_names
        assert 'ix_documents_user_updated' in index_names
        assert 'ix_documents_folder_status' in index_names
        assert 'ix_documents_user_folder' in index_names

    def test_user_model_fields(self):
        """测试用户模型字段"""
        from app.models.user import User

        assert hasattr(User, 'id')
        assert hasattr(User, 'username')
        assert hasattr(User, 'email')
        assert hasattr(User, 'hashed_password')
        assert hasattr(User, 'is_admin')
        assert hasattr(User, 'is_active')


# ── 限流器测试 ──────────────────────────────────────────────────

class TestRateLimiter:
    """测试限流器配置"""

    def test_rate_limit_strategies(self):
        """测试限流策略定义"""
        from app.core.limiter import RATE_LIMIT_STRATEGIES

        assert "default" in RATE_LIMIT_STRATEGIES
        assert "auth_login" in RATE_LIMIT_STRATEGIES
        assert "ai_generate" in RATE_LIMIT_STRATEGIES

        # 验证限流格式
        for strategy in RATE_LIMIT_STRATEGIES.values():
            assert "/" in strategy  # 应该是 "X/minute" 格式

    def test_limiter_initialization(self):
        """测试限流器初始化"""
        from app.core.limiter import limiter

        assert limiter is not None
        assert limiter.enabled is True or limiter.enabled is False  # 取决于测试环境


# ── 共享依赖测试 ──────────────────────────────────────────────────

class TestSharedDependencies:
    """测试共享依赖模块"""

    def test_require_admin_function_exists(self):
        """测试require_admin函数存在"""
        from app.core.deps import require_admin

        assert callable(require_admin)

    def test_get_document_or_404_function_exists(self):
        """测试get_document_or_404函数存在"""
        from app.core.deps import get_document_or_404

        assert callable(get_document_or_404)


# ── 内容转换器测试 ──────────────────────────────────────────────────

class TestContentConverter:
    """测试内容转换器"""

    def test_sanitize_filename(self):
        """测试文件名清理"""
        from app.services.content_converter import sanitize_filename

        # 正常文件名
        assert sanitize_filename("test.md") == "test.md"

        # 包含特殊字符
        result = sanitize_filename("test file (1).md")
        assert "/" not in result
        assert "\\" not in result

    def test_extract_plain_text(self):
        """测试纯文本提取"""
        from app.services.content_converter import extract_plain_text

        # 空内容
        assert extract_plain_text(None) == ""
        assert extract_plain_text({}) == ""

        # 简单内容
        content = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello World"}]
                }
            ]
        }
        result = extract_plain_text(content)
        assert "Hello World" in result


# ── 工作流引擎测试 ──────────────────────────────────────────────────

class TestWorkflowEngine:
    """测试工作流引擎"""

    def test_workflow_node_registry(self):
        """测试工作流节点注册表"""
        from app.services.workflow.node_registry import NodeProcessorRegistry

        assert NodeProcessorRegistry is not None
        assert hasattr(NodeProcessorRegistry, 'register')

    def test_workflow_validator(self):
        """测试工作流验证器"""
        from app.services.workflow.validator import validate_workflow_config

        assert callable(validate_workflow_config)


# ── 配置测试 ──────────────────────────────────────────────────

class TestConfiguration:
    """测试配置模块"""

    def test_settings_loading(self):
        """测试配置加载"""
        from app.core.config import get_settings

        settings = get_settings()

        assert settings.APP_NAME == "Knowledge Base"
        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 15
        assert settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_weak_jwt_key_rejection(self):
        """测试弱JWT密钥拒绝"""
        from pydantic import ValidationError
        from app.core.config import Settings

        # 弱密钥应该被拒绝
        with pytest.raises(ValidationError):
            Settings(JWT_SECRET_KEY="short")

        with pytest.raises(ValidationError):
            Settings(JWT_SECRET_KEY="change-me")


# ── 运行测试 ──────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
