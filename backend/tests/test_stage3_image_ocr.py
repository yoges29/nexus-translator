import io
from PIL import Image

from app.models.translation import TranslationHistory
from app.services.providers.ocr import BoundingBox, OCRRegion, OCRResult


def _generate_test_image(fmt: str = "PNG", size: tuple[int, int] = (200, 100)) -> bytes:
    img = Image.new("RGB", size, color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class AsyncMockOCR:
    def __init__(self, text: str = "Bonjour le monde", language: str = "fr", regions=None):
        self.text = text
        self.language = language
        self.regions = regions or [
            OCRRegion(
                text="Bonjour",
                bounding_box=BoundingBox(x=10, y=10, width=80, height=25),
                confidence=0.98,
            ),
            OCRRegion(
                text="le monde",
                bounding_box=BoundingBox(x=95, y=10, width=90, height=25),
                confidence=0.95,
            ),
        ]

    async def process_image(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(text=self.text, language=self.language, regions=self.regions)


def test_ocr_extract_png_success(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockOCR(text="Bonjour le monde", language="fr")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("PNG")
    response = client.post(
        "/api/ocr/extract",
        files={"image": ("sample.png", io.BytesIO(img_bytes), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Bonjour le monde"
    assert data["language"] == "fr"
    assert len(data["regions"]) == 2
    assert data["regions"][0]["text"] == "Bonjour"
    assert data["regions"][0]["bounding_box"]["x"] == 10
    assert data["regions"][0]["bounding_box"]["width"] == 80


def test_ocr_extract_file_field_alternative(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockOCR(text="Hello from file field", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("JPEG")
    response = client.post(
        "/api/ocr/extract",
        files={"file": ("sample.jpg", io.BytesIO(img_bytes), "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Hello from file field"


def test_ocr_extract_unsupported_format(client, mock_provider):
    response = client.post(
        "/api/ocr/extract",
        files={"image": ("malicious.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")},
    )
    assert response.status_code == 400
    assert "Unsupported image format" in response.json()["detail"]


def test_image_translate_jpg_success(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockOCR(text="Hello world", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("JPEG")
    response = client.post(
        "/api/image/translate",
        files={"image": ("test.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"target_language": "ta", "source_language": "en", "translation_style": "general"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_language"] == "en"
    assert data["target_language"] == "ta"
    assert data["extracted_text"] == "Hello world"
    assert "translated_text" in data
    assert len(data["translated_text"]) > 0
    assert data["history_id"] is not None
    assert len(data["regions"]) == 2


def test_image_translate_webp_success(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockOCR(text="Good morning", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("WEBP")
    response = client.post(
        "/api/image/translate",
        files={"file": ("test.webp", io.BytesIO(img_bytes), "image/webp")},
        data={"target_language": "es", "source_language": "auto"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_language"] == "es"
    assert data["extracted_text"] == "Good morning"
    assert "translated_text" in data


def test_image_translate_auto_language_detection(client, mock_provider, monkeypatch):
    # OCR returns no explicit language, testing automatic detection fallback
    mock_ocr = AsyncMockOCR(text="வணக்கம் எப்படி இருக்கிறீர்கள்", language=None, regions=[])
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("PNG")
    response = client.post(
        "/api/image/translate",
        files={"image": ("tamil_text.png", io.BytesIO(img_bytes), "image/png")},
        data={"target_language": "en", "source_language": "auto"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_language"] == "ta"
    assert data["target_language"] == "en"
    assert data["detected_language"] == "ta"


def test_image_translate_no_text_detected(client, mock_provider, monkeypatch):
    empty_ocr = AsyncMockOCR(text="   ", language=None, regions=[])
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: empty_ocr)

    img_bytes = _generate_test_image("PNG")
    response = client.post(
        "/api/image/translate",
        files={"image": ("blank.png", io.BytesIO(img_bytes), "image/png")},
        data={"target_language": "en"},
    )
    assert response.status_code == 400
    assert "No text was detected" in response.json()["detail"]


def test_image_translate_same_source_and_target_error(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockOCR(text="Same language text", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("PNG")
    response = client.post(
        "/api/image/translate",
        files={"image": ("test.png", io.BytesIO(img_bytes), "image/png")},
        data={"target_language": "en", "source_language": "en"},
    )
    assert response.status_code == 400
    assert "Source and target languages must be different" in response.json()["detail"]


def test_image_oversized_payload_rejection(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    orig_limit = settings.max_image_size_bytes
    settings.max_image_size_bytes = 200  # 200 bytes limit
    try:
        big_bytes = b"0" * 800
        response = client.post(
            "/api/image/translate",
            files={"image": ("big.png", io.BytesIO(big_bytes), "image/png")},
            data={"target_language": "es"},
        )
        assert response.status_code == 413
    finally:
        settings.max_image_size_bytes = orig_limit


def test_image_translation_history_persisted(client, mock_provider, db_session, monkeypatch):
    mock_ocr = AsyncMockOCR(text="Persist this OCR image", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("PNG")
    response = client.post(
        "/api/image/translate",
        files={"image": ("persist.png", io.BytesIO(img_bytes), "image/png")},
        data={"target_language": "hi", "source_language": "en"},
    )
    assert response.status_code == 200
    hist_id = response.json()["history_id"]

    record = db_session.get(TranslationHistory, hist_id)
    assert record is not None
    assert record.input_method == "image"
    assert record.source_language == "en"
    assert record.target_language == "hi"
    assert record.original_text == "Persist this OCR image"


def test_image_translate_speech_synthesis_integration(client, mock_provider, mock_tts, monkeypatch):
    mock_ocr = AsyncMockOCR(text="Audio playback test", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _generate_test_image("PNG")
    trans_res = client.post(
        "/api/image/translate",
        files={"image": ("speak.png", io.BytesIO(img_bytes), "image/png")},
        data={"target_language": "es", "source_language": "en"},
    )
    assert trans_res.status_code == 200
    translated_text = trans_res.json()["translated_text"]

    # Test synthesizing speech for translated text using Stage 2 TTS endpoint
    synth_res = client.post(
        "/api/speech/synthesize",
        json={"text": translated_text, "language": "es", "speed": 1.0},
    )
    assert synth_res.status_code == 200
    assert synth_res.headers["content-type"] in ("audio/mpeg", "audio/wav")
    assert len(synth_res.content) > 0
