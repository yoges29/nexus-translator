import io
import pytest
from starlette.testclient import TestClient

from app.core.errors import AppError, ProviderError
from app.services.providers.hybrid import HybridTranslationProvider
from app.services.providers.offline import OfflineLocalTranslationProvider


@pytest.fixture
def anyio_backend():
    return "asyncio"



# ---------------------------------------------------------------------------
# Offline Provider Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_offline_provider_supported_pairs():
    provider = OfflineLocalTranslationProvider()
    assert provider.is_pair_supported("en", "ta")
    assert provider.is_pair_supported("ta", "en")
    assert provider.is_pair_supported("en", "es")
    assert provider.is_pair_supported("en", "fr")
    assert provider.is_pair_supported("en", "de")
    assert provider.is_pair_supported("en", "hi")
    assert not provider.is_pair_supported("zh", "ar")
    assert not provider.is_pair_supported("ta", "de")


@pytest.mark.anyio
async def test_offline_provider_translations():
    provider = OfflineLocalTranslationProvider()

    # en -> ta
    res_ta = await provider.translate("Hello", "en", "ta")
    assert "வணக்கம்" in res_ta

    res_thanks = await provider.translate("Thank you", "en", "ta")
    assert "நன்றி" in res_thanks

    # ta -> en
    res_en = await provider.translate("வணக்கம்", "ta", "en")
    assert "Hello" in res_en

    # en -> es
    res_es = await provider.translate("Hello", "en", "es")
    assert "hola" in res_es.lower()

    # en -> fr
    res_fr = await provider.translate("Hello", "en", "fr")
    assert "bonjour" in res_fr.lower()

    # en -> de
    res_de = await provider.translate("Hello", "en", "de")
    assert "hallo" in res_de.lower()

    # en -> hi
    res_hi = await provider.translate("Hello", "en", "hi")
    assert "नमस्ते" in res_hi


@pytest.mark.anyio
async def test_offline_provider_unsupported_pair_raises_error():
    provider = OfflineLocalTranslationProvider()
    with pytest.raises(AppError) as exc_info:
        await provider.translate("Hello", "zh", "ja")
    assert "Offline translation is not supported" in exc_info.value.message


# ---------------------------------------------------------------------------
# Hybrid Provider Tests
# ---------------------------------------------------------------------------


class MockOnlineSuccessProvider:
    is_offline = False

    async def translate(self, text, source, target, style="general"):
        return f"[ONLINE] {text}"

    async def detect_language(self, text):
        from app.services.providers.base import DetectionResult
        return DetectionResult(language="en", confidence=0.99)

    async def get_alternatives(self, text, source, target, style="general"):
        return [f"[ALT] {text}"]


class MockOnlineFailingProvider:
    is_offline = False

    async def translate(self, text, source, target, style="general"):
        raise ProviderError("Cloud API network unreachable")

    async def detect_language(self, text):
        raise ProviderError("Cloud API network unreachable")

    async def get_alternatives(self, text, source, target, style="general"):
        raise ProviderError("Cloud API network unreachable")


@pytest.mark.anyio
async def test_hybrid_provider_online_mode():
    online = MockOnlineSuccessProvider()
    offline = OfflineLocalTranslationProvider()
    hybrid = HybridTranslationProvider(online_provider=online, offline_provider=offline)

    res = await hybrid.translate("Hello", "en", "ta", mode="online")
    assert res == "[ONLINE] Hello"
    meta = hybrid.get_last_meta()
    assert meta["is_offline"] is False
    assert meta["provider_used"] == "online"


@pytest.mark.anyio
async def test_hybrid_provider_forced_offline_mode():
    online = MockOnlineSuccessProvider()
    offline = OfflineLocalTranslationProvider()
    hybrid = HybridTranslationProvider(online_provider=online, offline_provider=offline)

    res = await hybrid.translate("Hello", "en", "ta", mode="offline")
    assert "வணக்கம்" in res
    meta = hybrid.get_last_meta()
    assert meta["is_offline"] is True
    assert meta["provider_used"] == "offline_local"


@pytest.mark.anyio
async def test_hybrid_provider_auto_fallback_on_failure():
    failing_online = MockOnlineFailingProvider()
    offline = OfflineLocalTranslationProvider()
    hybrid = HybridTranslationProvider(online_provider=failing_online, offline_provider=offline)

    # In auto mode, online fails -> falls back to offline for supported pair
    res = await hybrid.translate("Hello", "en", "ta", mode="auto")
    assert "வணக்கம்" in res
    meta = hybrid.get_last_meta()
    assert meta["is_offline"] is True
    assert meta["provider_used"] == "offline_fallback"


@pytest.mark.anyio
async def test_hybrid_provider_auto_fallback_unsupported_pair_raises():
    failing_online = MockOnlineFailingProvider()
    offline = OfflineLocalTranslationProvider()
    hybrid = HybridTranslationProvider(online_provider=failing_online, offline_provider=offline)

    # In auto mode, online fails, and pair is NOT supported offline -> raises error
    with pytest.raises(ProviderError):
        await hybrid.translate("Hello", "zh", "ja", mode="auto")


# ---------------------------------------------------------------------------
# API Endpoint Tests
# ---------------------------------------------------------------------------


def test_offline_status_endpoint(client):
    response = client.get("/api/offline/status")
    assert response.status_code == 200
    data = response.json()
    assert "online_available" in data
    assert "current_mode" in data
    assert "supported_pairs" in data
    assert isinstance(data["supported_pairs"], list)
    assert len(data["supported_pairs"]) > 0


def test_translate_endpoint_offline_mode_success(client):
    response = client.post(
        "/api/translate",
        json={
            "source_language": "en",
            "target_language": "ta",
            "text": "Hello",
            "mode": "offline",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_language"] == "en"
    assert data["target_language"] == "ta"
    assert data["is_offline"] is True
    assert data["provider_used"] == "offline_local"
    assert "வணக்கம்" in data["translated_text"]


def test_translate_endpoint_offline_mode_unsupported_pair(client):
    response = client.post(
        "/api/translate",
        json={
            "source_language": "de",
            "target_language": "ta",
            "text": "Guten Tag",
            "mode": "offline",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "Offline Mode" in data["detail"] or "not supported" in data["detail"]


# ---------------------------------------------------------------------------
# Real-Time Voice WebSocket Streaming Tests
# ---------------------------------------------------------------------------


def test_voice_websocket_lifecycle(client):
    with client.websocket_connect("/api/voice/stream?source_language=en&target_language=ta") as ws:
        # 1. Ready frame
        ready_frame = ws.receive_json()
        assert ready_frame["type"] == "ready"
        assert ready_frame["source_language"] == "en"
        assert ready_frame["target_language"] == "ta"

        # 2. Ping / Pong
        ws.send_json({"type": "ping"})
        pong_frame = ws.receive_json()
        assert pong_frame["type"] == "pong"

        # 3. Config update
        ws.send_json({
            "type": "config",
            "source_language": "en",
            "target_language": "es",
            "translation_style": "formal",
        })
        cfg_frame = ws.receive_json()
        assert cfg_frame["type"] == "config_updated"
        assert cfg_frame["target_language"] == "es"

        # 4. Interim transcript
        ws.send_json({
            "type": "transcript",
            "text": "Hello",
            "is_final": False,
        })
        interim_frame = ws.receive_json()
        assert interim_frame["type"] == "interim"
        assert interim_frame["original_text"] == "Hello"

        # 5. Final transcript
        ws.send_json({
            "type": "transcript",
            "text": "Hello",
            "is_final": True,
        })
        final_frame = ws.receive_json()
        assert final_frame["type"] == "final"
        assert final_frame["original_text"] == "Hello"
        assert "translated_text" in final_frame
        assert "history_id" in final_frame


def test_voice_translate_speech_endpoint(client, mock_stt):
    fake_audio = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    response = client.post(
        "/api/voice/translate-speech",
        files={"file": ("recording.webm", fake_audio, "audio/webm")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["input_method"] == "voice"
    assert "translated_text" in data


def test_voice_websocket_binary_chunk_stream(client, mock_stt):
    with client.websocket_connect("/api/voice/stream?source_language=en&target_language=ta") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"

        # Send binary audio chunk (> 6000 bytes)
        fake_chunk = b"\x1a\x45\xdf\xa3" + (b"\x00" * 7000)
        ws.send_bytes(fake_chunk)

        # Expect final translation frame
        frame = ws.receive_json()
        assert frame["type"] == "final"
        assert frame["original_text"] == "Hello world speech"
        assert "translated_text" in frame

