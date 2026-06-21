from pydantic import BaseModel, constr, field_validator
from typing import Optional, Any
from datetime import datetime

class TagInfo(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True

class DocumentCreate(BaseModel):
    title: constr(min_length=1, max_length=500)
    content_json: Optional[Any] = None
    folder_id: Optional[int] = None

class DocumentUpdate(BaseModel):
    title: Optional[constr(min_length=1, max_length=500)] = None
    content_json: Optional[Any] = None
    latex_source: Optional[str] = None
    folder_id: Optional[int] = None

class DocumentResponse(BaseModel):
    id: int
    title: str
    content_json: Optional[Any] = None
    latex_source: Optional[str] = None
    status: str
    folder_id: Optional[int] = None
    version: int
    created_at: datetime
    updated_at: datetime
    tags: list[TagInfo] = []

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    """Lightweight document summary for list views — omits content_json."""
    id: int
    title: str
    status: str
    folder_id: Optional[int] = None
    version: int
    created_at: datetime
    updated_at: datetime
    tags: list[TagInfo] = []

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    total: int
    offset: int
    limit: int

class BatchDeleteRequest(BaseModel):
    ids: list[int]

    @field_validator("ids")
    @classmethod
    def validate_ids_length(cls, v: list[int]) -> list[int]:
        if len(v) > 1000:
            raise ValueError("一次最多批量操作 1000 个文档")
        return v

class BatchMoveRequest(BaseModel):
    ids: list[int]
    folder_id: Optional[int] = None

    @field_validator("ids")
    @classmethod
    def validate_ids_length(cls, v: list[int]) -> list[int]:
        if len(v) > 1000:
            raise ValueError("一次最多批量操作 1000 个文档")
        return v

class StatusUpdateRequest(BaseModel):
    status: str

class VersionResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class VersionDetailResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    title: str
    content_json: Optional[Any] = None
    created_at: datetime
