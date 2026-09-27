from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = 8000
    backend_port: int = 8000
    backend_host: str = "0.0.0.0"

    database_url: str = "postgresql+psycopg2://nexus:nexus_secret@localhost:5432/nexus_translator"
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    cors_origin_regex: str = r"^(https:\/\/.*\.vercel\.app|https:\/\/.*\.onrender\.com)$"
    max_text_length: int = 20000
    translation_timeout_seconds: int = 30
    rate_limit_per_minute: int = 60

    translation_provider: str = "libretranslate"
    translation_api_key: str = ""
    translation_api_url: str = "https://libretranslate.com"
    google_application_credentials: str = ""

    stt_provider: str = "speech_recognition"
    stt_api_key: str = ""
    tts_provider: str = "gtts"
    tts_api_key: str = ""
    max_audio_size_bytes: int = 10 * 1024 * 1024  # 10MB

    # Stage 3: OCR & Document Processing
    ocr_provider: str = "rapidocr"
    tesseract_cmd: str = ""
    cloud_vision_api_key: str = ""
    max_image_size_bytes: int = 10 * 1024 * 1024  # 10MB
    max_document_size_bytes: int = 20 * 1024 * 1024  # 20MB
    max_document_pages: int = 50
    documents_storage_dir: str = "temp_documents"

    @property
    def normalized_database_url(self) -> str:
        url = self.database_url.strip()
        if not url:
            return "sqlite:///./nexus_translator.db"
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def max_payload_size_bytes(self) -> int:
        return max(self.max_audio_size_bytes, self.max_image_size_bytes, self.max_document_size_bytes)

    @property
    def storage_path(self) -> Path:
        base = Path(__file__).resolve().parents[2] / self.documents_storage_dir
        base.mkdir(parents=True, exist_ok=True)
        return base

    @property
    def cors_origin_list(self) -> list[str]:
        origins = []
        for origin in self.cors_origins.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned:
                origins.append(cleaned)
        return origins

    @property
    def languages_path(self) -> Path:
        candidates = [
            Path(__file__).resolve().parent / "languages.json",
            Path(__file__).resolve().parents[3] / "shared" / "languages.json",
            Path(__file__).resolve().parents[2] / "shared" / "languages.json",
            Path("/shared/languages.json"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()
