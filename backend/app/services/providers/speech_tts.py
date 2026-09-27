import io
import logging

from app.core.errors import AppError, ProviderError
from app.services.providers.base import SynthesisResult, TextToSpeechProvider

logger = logging.getLogger("nexus.translator.provider.tts")

# Mapping of ISO language codes to gTTS language codes
GTTS_LANG_MAP: dict[str, str] = {
    "en": "en",
    "ta": "ta",
    "hi": "hi",
    "te": "te",
    "ml": "ml",
    "kn": "kn",
    "ja": "ja",
    "ko": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "zh": "zh-CN",
    "ar": "ar",
}


class GTTSTextToSpeechProvider(TextToSpeechProvider):
    """Google Text-to-Speech (gTTS) implementation with in-memory synthesis."""

    async def synthesize(
        self,
        text: str,
        language: str,
        speed: float = 1.0,
        voice: str | None = None,
    ) -> SynthesisResult:
        cleaned = text.strip()
        if not cleaned:
            raise AppError("Text cannot be empty.")

        lang_code = language.strip().lower()
        tld_code = GTTS_LANG_MAP.get(lang_code, lang_code)

        try:
            from gtts import gTTS

            # gTTS supports slow=True (around 0.7x speed)
            is_slow = speed < 0.9

            # Generate speech into memory
            tts = gTTS(text=cleaned, lang=tld_code, slow=is_slow)
            output_io = io.BytesIO()
            tts.write_to_fp(output_io)
            audio_bytes = output_io.getvalue()

            if not audio_bytes:
                raise ProviderError("Synthesizer generated empty audio.")

            return SynthesisResult(
                audio_bytes=audio_bytes,
                content_type="audio/mpeg",
                format="mp3",
            )
        except ValueError as exc:
            logger.warning("gTTS unsupported language: %s", lang_code)
            raise AppError(f"Language '{language}' is not supported for voice synthesis.") from exc
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("Unexpected TTS synthesis failure: %s", exc)
            raise ProviderError("Text-to-speech service is temporarily unavailable. Please try again.") from exc


class MockTTSProvider(TextToSpeechProvider):
    """Deterministic Mock TTS Provider for automated testing and offline fallback."""

    async def synthesize(
        self,
        text: str,
        language: str,
        speed: float = 1.0,
        voice: str | None = None,
    ) -> SynthesisResult:
        cleaned = text.strip()
        if not cleaned:
            raise AppError("Text cannot be empty.")
        if language == "unsupported":
            raise AppError("Language 'unsupported' is not supported for voice synthesis.")

        # Minimal valid MP3 header / dummy audio bytes
        mock_mp3 = b"\xff\xfb\x90\x44\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" * 8
        return SynthesisResult(
            audio_bytes=mock_mp3,
            content_type="audio/mpeg",
            format="mp3",
        )
