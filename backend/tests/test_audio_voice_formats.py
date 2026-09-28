import io
import subprocess
import pytest
from app.services.providers.speech_stt import (
    SpeechRecognitionSTTProvider,
    detect_audio_format,
    find_ffmpeg_executable,
)


def _generate_test_audio(fmt: str) -> bytes:
    """Generate minimal valid test audio container using ffmpeg."""
    ffmpeg = find_ffmpeg_executable() or "ffmpeg"
    if fmt == "webm":
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=0.5",
            "-c:a",
            "libopus",
            "-f",
            "webm",
            "pipe:1",
        ]
    elif fmt == "mp4":
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=0.5",
            "-c:a",
            "aac",
            "-f",
            "mp4",
            "-movflags",
            "frag_keyframe+empty_moov",
            "pipe:1",
        ]
    elif fmt == "wav":
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=0.5",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "wav",
            "pipe:1",
        ]
    else:
        raise ValueError(f"Unsupported test format: {fmt}")

    res = subprocess.run(cmd, capture_output=True, check=True)
    return res.stdout


def test_detect_audio_format_magic_bytes():
    webm_bytes = _generate_test_audio("webm")
    fmt, ext = detect_audio_format(webm_bytes)
    assert fmt == "webm"
    assert ext == ".webm"

    wav_bytes = _generate_test_audio("wav")
    fmt, ext = detect_audio_format(wav_bytes)
    assert fmt == "wav"
    assert ext == ".wav"


def test_detect_audio_format_by_filename():
    fmt, ext = detect_audio_format(b"dummydata", filename="speech.webm")
    assert fmt == "webm"
    assert ext == ".webm"

    fmt, ext = detect_audio_format(b"dummydata", filename="recording.mp4")
    assert fmt == "mp4"
    assert ext == ".mp4"

    fmt, ext = detect_audio_format(b"dummydata", filename="voice.wav")
    assert fmt == "wav"
    assert ext == ".wav"


def test_detect_audio_format_by_content_type():
    fmt, ext = detect_audio_format(b"dummydata", content_type="audio/webm;codecs=opus")
    assert fmt == "webm"
    assert ext == ".webm"

    fmt, ext = detect_audio_format(b"dummydata", content_type="audio/mp4")
    assert fmt == "mp4"
    assert ext == ".mp4"


def test_convert_to_wav_bytes_webm():
    provider = SpeechRecognitionSTTProvider()
    webm_bytes = _generate_test_audio("webm")
    wav_bytes = provider._convert_to_wav_bytes(webm_bytes, content_type="audio/webm", filename="recording.webm")
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[:16]


def test_convert_to_wav_bytes_wav_passthrough():
    provider = SpeechRecognitionSTTProvider()
    wav_bytes = _generate_test_audio("wav")
    converted = provider._convert_to_wav_bytes(wav_bytes, content_type="audio/wav", filename="recording.wav")
    assert converted == wav_bytes


def test_stt_transcribe_webm_endpoint(client, mock_stt):
    webm_bytes = _generate_test_audio("webm")
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("recording.webm", io.BytesIO(webm_bytes), "audio/webm;codecs=opus")},
        data={"language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Hello world speech"
    assert data["confidence"] is not None


def test_stt_transcribe_mp4_endpoint(client, mock_stt):
    mp4_bytes = _generate_test_audio("mp4")
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("recording.mp4", io.BytesIO(mp4_bytes), "audio/mp4")},
        data={"language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Hello world speech"


def test_voice_translate_speech_endpoint(client, mock_stt):
    webm_bytes = _generate_test_audio("webm")
    response = client.post(
        "/api/voice/translate-speech",
        files={"file": ("recording.webm", io.BytesIO(webm_bytes), "audio/webm")},
        data={"target_language": "es", "source_language": "en", "translation_style": "general"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["input_method"] == "voice"
    assert "original_text" in data
    assert "translated_text" in data
