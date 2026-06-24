from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import secrets

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Knowledge Base"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/knowledge.db"

    # JWT
    JWT_SECRET_KEY: str  # No default - must be set in environment
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    LLM_PROVIDER: str = "openai"  # openai | anthropic | ollama
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "gpt-4o"

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024

    # Security
    MAX_UPLOAD_SIZE_MB: int = 10
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AI: str = "10/minute"
    ADMIN_INITIAL_PASSWORD: str = ""  # If empty, generates random password
    CORS_ORIGINS: str = "http://localhost:3000"  # Comma-separated origins
    INTERNAL_API_SECRET: str = ""  # Required for server-to-server API calls

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret key strength."""
        WEAK_KEYS = {
            "dev-secret-change-in-production",
            "dev-secret-key-change-in-production-use-long-random-string",
            "secret",
            "change-me",
            "your-secret-key",
            "jwt-secret",
        }
        if v in WEAK_KEYS:
            raise ValueError(
                "JWT_SECRET_KEY is a known weak value. "
                "Generate a strong key with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. "
                "Generate a strong key with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
