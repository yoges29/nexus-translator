import io
from app.services.detector import LanguageDetector


def test_detect_language_endpoint_tamil(client, mock_provider):
    response = client.post("/api/detect-language", json={"text": "வணக்கம், எப்படி இருக்கிறீர்கள்?"})
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"  # from mock_provider
    assert "language_name" in data


def test_detect_language_real_detector_languages():
    # Direct test of real LanguageDetector
    ta_result = LanguageDetector.detect("வணக்கம், எப்படி இருக்கிறீர்கள்?")
    assert ta_result.language == "ta"
    assert ta_result.confidence is not None

    hi_result = LanguageDetector.detect("नमस्ते, आप कैसे हैं?")
    assert hi_result.language == "hi"
    assert hi_result.confidence is not None

    ja_result = LanguageDetector.detect("こんにちは、元気ですか？")
    assert ja_result.language == "ja"
    assert ja_result.confidence is not None

    en_result = LanguageDetector.detect("Hello world, how are you doing today?")
    assert en_result.language == "en"


def test_detect_language_empty_input(client, mock_provider):
    response = client.post("/api/detect-language", json={"text": "   "})
    assert response.status_code == 422 or response.status_code == 400


def test_detect_language_provider_failure(client, failing_provider):
    response = client.post("/api/detect-language", json={"text": "Hello"})
    assert response.status_code == 503


def test_alternatives_endpoint_success(client, mock_provider):
    response = client.post(
        "/api/translate/alternatives",
        json={"source_language": "en", "target_language": "ta", "text": "How are you?", "translation_style": "general"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "primary" in data
    assert "alternatives" in data
    assert isinstance(data["alternatives"], list)
    assert len(data["alternatives"]) <= 3


def test_alternatives_endpoint_invalid_language(client, mock_provider):
    response = client.post(
        "/api/translate/alternatives",
        json={"source_language": "en", "target_language": "unsupported_lang", "text": "Hello"},
    )
    assert response.status_code == 400


def test_alternatives_endpoint_failure(client, failing_provider):
    response = client.post(
        "/api/translate/alternatives",
        json={"source_language": "en", "target_language": "ta", "text": "Hello"},
    )
    assert response.status_code == 503


def test_translation_styles(client, mock_provider):
    for style in ["general", "formal", "casual"]:
        response = client.post(
            "/api/translate",
            json={
                "source_language": "en",
                "target_language": "ta",
                "text": "How are you?",
                "translation_style": style,
                "input_method": "text",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["translation_style"] == style
        assert data["input_method"] == "text"


def test_stt_transcribe_success(client, mock_stt):
    fake_wav = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("recording.wav", fake_wav, "audio/wav")},
        data={"language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Hello world speech"
    assert data["confidence"] is not None


def test_stt_transcribe_empty_file(client, mock_stt):
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("recording.wav", empty_file, "audio/wav")},
    )
    assert response.status_code == 400


def test_tts_synthesize_success(client, mock_tts):
    response = client.post(
        "/api/speech/synthesize",
        json={"text": "Hello, how are you?", "language": "en", "speed": 1.0},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert len(response.content) > 0


def test_tts_synthesize_empty_text(client, mock_tts):
    response = client.post(
        "/api/speech/synthesize",
        json={"text": "   ", "language": "en"},
    )
    assert response.status_code == 422 or response.status_code == 400


def test_tts_synthesize_unsupported_language(client, mock_tts):
    response = client.post(
        "/api/speech/synthesize",
        json={"text": "Hello", "language": "nonexistent_lang"},
    )
    assert response.status_code == 400
