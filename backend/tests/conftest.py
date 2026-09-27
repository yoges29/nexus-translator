from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app.services import provider_factory
from app.services.cache import detection_cache, translation_cache, word_cache


@pytest.fixture(autouse=True)
def _clear_translation_caches():
    translation_cache.clear()
    detection_cache.clear()
    word_cache.clear()
    yield
    translation_cache.clear()
    detection_cache.clear()
    word_cache.clear()


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session, monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr("app.main.init_db", lambda: None)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_provider(monkeypatch):
    provider = MagicMock()
    provider.translate = AsyncMock(return_value="வணக்கம்")
    provider.detect_language = AsyncMock(
        return_value=type("Det", (), {"language": "en", "confidence": 0.99})()
    )
    provider.get_alternatives = AsyncMock(
        return_value=["எப்படி இருக்கீங்க?", "நலமாக இருக்கிறீர்களா?"]
    )

    provider_factory.get_translation_provider.cache_clear()
    monkeypatch.setattr(provider_factory, "get_translation_provider", lambda: provider)
    monkeypatch.setattr("app.services.translation_service.get_translation_provider", lambda: provider)
    monkeypatch.setattr("app.services.document_service.get_translation_provider", lambda: provider)
    monkeypatch.setattr("app.services.conversation_service.get_translation_provider", lambda: provider)
    return provider


@pytest.fixture
def failing_provider(monkeypatch):
    from app.core.errors import ProviderError

    provider = MagicMock()

    async def fail_translate(*_args, **_kwargs):
        raise ProviderError("Translation service is temporarily unavailable. Please try again.")

    async def fail_detect(*_args, **_kwargs):
        raise ProviderError("Translation service is temporarily unavailable. Please try again.")

    async def fail_alternatives(*_args, **_kwargs):
        raise ProviderError("Translation service is temporarily unavailable. Please try again.")

    provider.translate = fail_translate
    provider.detect_language = fail_detect
    provider.get_alternatives = fail_alternatives
    monkeypatch.setattr(provider_factory, "get_translation_provider", lambda: provider)
    monkeypatch.setattr("app.services.translation_service.get_translation_provider", lambda: provider)
    monkeypatch.setattr("app.services.document_service.get_translation_provider", lambda: provider)
    monkeypatch.setattr("app.services.conversation_service.get_translation_provider", lambda: provider)
    return provider


@pytest.fixture
def mock_stt(monkeypatch):
    from app.services.providers.base import TranscriptionResult

    stt = MagicMock()
    stt.transcribe = AsyncMock(
        return_value=TranscriptionResult(text="Hello world speech", language="en", confidence=0.98)
    )
    provider_factory.get_stt_provider.cache_clear()
    monkeypatch.setattr(provider_factory, "get_stt_provider", lambda: stt)
    monkeypatch.setattr("app.services.translation_service.get_stt_provider", lambda: stt)
    monkeypatch.setattr("app.services.conversation_service.get_stt_provider", lambda: stt)
    return stt


@pytest.fixture
def mock_tts(monkeypatch):
    from app.services.providers.base import SynthesisResult

    tts = MagicMock()
    tts.synthesize = AsyncMock(
        return_value=SynthesisResult(audio_bytes=b"\xff\xfb\x90\x44" * 10, content_type="audio/mpeg", format="mp3")
    )
    provider_factory.get_tts_provider.cache_clear()
    monkeypatch.setattr(provider_factory, "get_tts_provider", lambda: tts)
    monkeypatch.setattr("app.services.translation_service.get_tts_provider", lambda: tts)
    return tts


@pytest.fixture
def mock_ocr(monkeypatch):
    from app.services.providers.ocr import BoundingBox, OCRRegion, OCRResult

    ocr = MagicMock()
    ocr.process_image = AsyncMock(
        return_value=OCRResult(
            text="Hello world OCR",
            language="en",
            regions=[
                OCRRegion(
                    text="Hello",
                    bounding_box=BoundingBox(x=10, y=10, width=50, height=20),
                    confidence=0.99,
                )
            ],
        )
    )
    ocr.extract_text = AsyncMock(return_value="Hello world OCR")
    provider_factory.get_ocr_provider.cache_clear()
    monkeypatch.setattr(provider_factory, "get_ocr_provider", lambda: ocr)
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: ocr)
    monkeypatch.setattr("app.services.document_service.get_ocr_provider", lambda: ocr)
    return ocr



