from pydantic import BaseModel, Field
from typing import Any, Generic, Optional, TypeVar
from enum import Enum

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorCode(str, Enum):
    """统一错误码体系"""
    # 认证错误 (1xxx)
    AUTH_INVALID_CREDENTIALS = "AUTH_1001"
    AUTH_TOKEN_EXPIRED = "AUTH_1002"
    AUTH_TOKEN_INVALID = "AUTH_1003"
    AUTH_ACCOUNT_DISABLED = "AUTH_1004"
    AUTH_INSUFFICIENT_PERMISSION = "AUTH_1005"
    AUTH_PASSWORD_MISMATCH = "AUTH_1006"

    # 资源错误 (2xxx)
    RESOURCE_NOT_FOUND = "RES_2001"
    RESOURCE_ALREADY_EXISTS = "RES_2002"
    RESOURCE_CONFLICT = "RES_2003"
    RESOURCE_LIMIT_EXCEEDED = "RES_2004"

    # 验证错误 (3xxx)
    VALIDATION_ERROR = "VAL_3001"
    INVALID_FILE_FORMAT = "VAL_3002"
    FILE_TOO_LARGE = "VAL_3003"
    INVALID_STATUS_VALUE = "VAL_3004"

    # AI/外部服务错误 (4xxx)
    AI_SERVICE_UNAVAILABLE = "AI_4001"
    AI_ANALYSIS_FAILED = "AI_4002"
    EMBEDDING_FAILED = "AI_4003"
    LLM_CONNECTION_FAILED = "AI_4004"

    # 速率限制 (5xxx)
    RATE_LIMIT_EXCEEDED = "RATE_5001"

    # 系统错误 (9xxx)
    INTERNAL_ERROR = "SYS_9001"
    DATABASE_ERROR = "SYS_9002"
    EXTERNAL_SERVICE_ERROR = "SYS_9003"


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应包装器"""
    success: bool = True
    code: str = "OK"
    message: str = ""
    data: Optional[T] = None
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """统一错误响应"""
    success: bool = False
    code: str
    message: str
    details: list[ErrorDetail] = []
    request_id: Optional[str] = None


class PaginationMeta(BaseModel):
    """分页元数据"""
    total: int
    offset: int
    limit: int
    has_more: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应"""
    success: bool = True
    code: str = "OK"
    data: list[T]
    pagination: PaginationMeta
    request_id: Optional[str] = None


# 兼容旧格式
class MessageResponse(BaseModel):
    """简单消息响应（兼容旧格式）"""
    message: str
