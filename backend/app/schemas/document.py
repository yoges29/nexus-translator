from datetime import datetime
from pydantic import BaseModel


class DocumentItem(BaseModel):
    id: int
    user_id: int | None = None
    filename: str
    document_type: str
    file_size: int
    source_language: str
    target_language: str
    page_count: int
    original_text_sample: str
    translated_text_sample: str
    status: str
    download_filename: str
    download_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentItem]
    total: int
