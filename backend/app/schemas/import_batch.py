from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ImportFileResponse(BaseModel):
    id: int
    batch_id: int
    filename: str
    file_type: str
    status: str
    ai_analysis: Optional[dict] = None
    error_message: Optional[str] = None
    imported_document_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ImportBatchResponse(BaseModel):
    id: int
    status: str
    total_files: int
    processed_count: int
    created_at: datetime
    files: list[ImportFileResponse] = []

    class Config:
        from_attributes = True


class ImportBatchListResponse(BaseModel):
    batches: list[ImportBatchResponse]


class ImportFileUpdateRequest(BaseModel):
    """User can edit AI suggestions before approving."""
    ai_analysis: Optional[dict] = None


class ImportApproveRequest(BaseModel):
    file_ids: list[int]
