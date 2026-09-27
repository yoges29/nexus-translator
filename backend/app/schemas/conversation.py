from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class CreateSessionRequest(BaseModel):
    language_a: str = Field(..., min_length=2, max_length=16)
    language_b: str = Field(..., min_length=2, max_length=16)
    title: str | None = Field(default=None, max_length=255)


class UpdateSessionRequest(BaseModel):
    language_a: str | None = Field(default=None, min_length=2, max_length=16)
    language_b: str | None = Field(default=None, min_length=2, max_length=16)
    title: str | None = Field(default=None, max_length=255)


class SendMessageRequest(BaseModel):
    speaker: Literal["speaker_a", "speaker_b"]
    text: str = Field(..., min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message text cannot be empty.")
        return cleaned


class ConversationMessageItem(BaseModel):
    id: int
    session_id: int
    speaker: str
    source_language: str
    target_language: str
    original_text: str
    translated_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSessionItem(BaseModel):
    id: int
    user_id: int | None = None
    title: str
    language_a: str
    language_b: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    messages: list[ConversationMessageItem] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConversationSessionListResponse(BaseModel):
    items: list[ConversationSessionItem]
    total: int
