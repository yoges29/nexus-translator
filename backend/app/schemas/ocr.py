from pydantic import BaseModel, Field


class BoundingBoxSchema(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OCRRegionSchema(BaseModel):
    text: str
    bounding_box: BoundingBoxSchema
    confidence: float | None = None
    translated_text: str | None = None



class OCRExtractResponse(BaseModel):
    text: str
    language: str | None = None
    regions: list[OCRRegionSchema] = Field(default_factory=list)


class ImageTranslateResponse(BaseModel):
    source_language: str
    target_language: str
    extracted_text: str
    translated_text: str
    detected_language: str | None = None
    translation_style: str = "general"
    regions: list[OCRRegionSchema] = Field(default_factory=list)
    history_id: int | None = None
