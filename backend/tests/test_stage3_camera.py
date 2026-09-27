import io
from PIL import Image

from app.services.providers.ocr import BoundingBox, OCRRegion, OCRResult


def _create_camera_frame(format: str = "JPEG", size: tuple[int, int] = (640, 480)) -> bytes:
    """Simulates a captured frame from a browser video element."""
    img = Image.new("RGB", size, color=(245, 245, 245))
    buf = io.BytesIO()
    img.save(buf, format=format, quality=90)
    return buf.getvalue()


class AsyncMockCameraOCR:
    def __init__(self, text: str = "Welcome to Nexus", language: str = "en", regions=None):
        self.text = text
        self.language = language
        self.regions = regions or [
            OCRRegion(
                text="Welcome to Nexus",
                bounding_box=BoundingBox(x=50, y=50, width=200, height=40),
                confidence=0.97,
            )
        ]

    async def process_image(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(text=self.text, language=self.language, regions=self.regions)


def test_camera_capture_translation_success(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockCameraOCR(text="Camera captured text", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    frame_bytes = _create_camera_frame("JPEG")
    response = client.post(
        "/api/image/translate",
        files={"image": ("camera_capture.jpg", io.BytesIO(frame_bytes), "image/jpeg")},
        data={"target_language": "ta", "source_language": "en", "translation_style": "general"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_language"] == "en"
    assert data["target_language"] == "ta"
    assert data["extracted_text"] == "Camera captured text"
    assert "translated_text" in data
    assert data["history_id"] is not None


def test_camera_capture_auto_detection(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockCameraOCR(text="வணக்கம் உலகம்", language=None, regions=[])
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    frame_bytes = _create_camera_frame("JPEG")
    response = client.post(
        "/api/image/translate",
        files={"file": ("camera_frame.jpg", io.BytesIO(frame_bytes), "image/jpeg")},
        data={"target_language": "en", "source_language": "auto"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_language"] == "ta"
    assert data["target_language"] == "en"
    assert data["detected_language"] == "ta"


def test_camera_capture_no_text_error(client, mock_provider, monkeypatch):
    empty_ocr = AsyncMockCameraOCR(text="   ", language=None, regions=[])
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: empty_ocr)

    frame_bytes = _create_camera_frame("JPEG")
    response = client.post(
        "/api/image/translate",
        files={"image": ("blank_frame.jpg", io.BytesIO(frame_bytes), "image/jpeg")},
        data={"target_language": "en"},
    )
    assert response.status_code == 400
    assert "No text was detected" in response.json()["detail"]


def test_camera_capture_tts_synthesis(client, mock_provider, mock_tts, monkeypatch):
    mock_ocr = AsyncMockCameraOCR(text="Voice playback", language="en")
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    frame_bytes = _create_camera_frame("JPEG")
    trans_res = client.post(
        "/api/image/translate",
        files={"image": ("camera_tts.jpg", io.BytesIO(frame_bytes), "image/jpeg")},
        data={"target_language": "es", "source_language": "en"},
    )
    assert trans_res.status_code == 200
    translated_text = trans_res.json()["translated_text"]

    synth_res = client.post(
        "/api/speech/synthesize",
        json={"text": translated_text, "language": "es", "speed": 1.0},
    )
    assert synth_res.status_code == 200
    assert synth_res.headers["content-type"] in ("audio/mpeg", "audio/wav")
    assert len(synth_res.content) > 0
