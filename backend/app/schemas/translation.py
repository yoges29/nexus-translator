from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TranslateRequest(BaseModel):
    source_language: str = Field(..., min_length=2, max_length=16)
    target_language: str = Field(..., min_length=2, max_length=16)
    text: str = Field(..., min_length=1)
    translation_style: Literal["general", "formal", "casual"] = "general"
    input_method: Literal["text", "voice"] = "text"
    mode: Literal["auto", "online", "offline"] = "auto"

    @field_validator("text")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be empty.")
        return cleaned


class TranslateResponse(BaseModel):
    source_language: str
    target_language: str
    original_text: str
    translated_text: str
    translation_style: str = "general"
    input_method: str = "text"
    detected_language: str | None = None
    history_id: int | None = None
    is_offline: bool = False
    provider_used: str = "online"


class OfflinePairItem(BaseModel):
    source: str
    target: str


class OfflineStatusResponse(BaseModel):
    online_available: bool
    current_mode: str = "auto"
    supported_pairs: list[OfflinePairItem]



class DetectLanguageRequest(BaseModel):
    text: str = Field(..., min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be empty.")
        return cleaned


class DetectLanguageResponse(BaseModel):
    language: str
    language_name: str | None = None
    confidence: float | None = None


class AlternativesRequest(BaseModel):
    source_language: str = Field(..., min_length=2, max_length=16)
    target_language: str = Field(..., min_length=2, max_length=16)
    text: str = Field(..., min_length=1)
    translation_style: Literal["general", "formal", "casual"] = "general"

    @field_validator("text")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be empty.")
        return cleaned


class AlternativesResponse(BaseModel):
    primary: str
    alternatives: list[str] = Field(default_factory=list, max_length=3)


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: str = Field(..., min_length=2, max_length=16)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    voice: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be empty.")
        return cleaned


class TranscribeResponse(BaseModel):
    text: str
    language: str | None = None
    confidence: float | None = None


class HistoryItem(BaseModel):
    id: int
    user_id: int | None
    source_language: str
    target_language: str
    original_text: str
    translated_text: str
    detected_language: str | None = None
    translation_style: str = "general"
    input_method: str = "text"
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int


class MultimodalHistoryItem(BaseModel):
    id: str
    raw_id: int
    modality: Literal["text", "voice", "image", "document", "conversation"]
    title: str
    source_language: str
    target_language: str
    original_text: str
    translated_text: str
    created_at: datetime
    document_type: str | None = None
    download_url: str | None = None
    session_id: int | None = None


class MultimodalHistoryResponse(BaseModel):
    items: list[MultimodalHistoryItem]
    total: int


class LanguageItem(BaseModel):
    code: str
    name: str
    nativeName: str
    direction: str
    translationSupported: bool

