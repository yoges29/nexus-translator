import io
import logging

from app.core.errors import AppError, ProviderError
from app.services.providers.base import SpeechToTextProvider, TranscriptionResult

logger = logging.getLogger("nexus.translator.provider.stt")

# BCP-47 mapping for speech recognition engines
LANGUAGE_LOCALE_MAP: dict[str, str] = {
    "en": "en-US",
    "ta": "ta-IN",
    "hi": "hi-IN",
    "te": "te-IN",
    "ml": "ml-IN",
    "kn": "kn-IN",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "zh": "zh-CN",
    "ar": "ar-SA",
}


class SpeechRecognitionSTTProvider(SpeechToTextProvider):
    """Speech-to-Text provider utilizing Python speech_recognition with robust audio decoding."""

    def _convert_to_wav_bytes(self, audio_bytes: bytes, content_type: str) -> bytes:
        # Check if already a valid RIFF WAV
        if audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]:
            return audio_bytes

        # Try pydub for converting WebM, OGG, MP3, M4A, etc.
        try:
            from pydub import AudioSegment

            format_hint = None
            if "webm" in content_type:
                format_hint = "webm"
            elif "ogg" in content_type:
                format_hint = "ogg"
            elif "mp3" in content_type or "mpeg" in content_type:
                format_hint = "mp3"
            elif "m4a" in content_type or "mp4" in content_type:
                format_hint = "mp4"

            segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=format_hint)
            output_io = io.BytesIO()
            segment.export(output_io, format="wav")
            return output_io.getvalue()
        except Exception as exc:
            logger.debug("pydub conversion skipped/failed: %s", exc)

        # If audio_bytes is already PCM or raw, return as is
        return audio_bytes

    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes or len(audio_bytes) < 32:
            raise AppError("Audio file is empty or invalid.")

        import speech_recognition as sr

        wav_data = self._convert_to_wav_bytes(audio_bytes, content_type)
        recognizer = sr.Recognizer()

        try:
            with sr.AudioFile(io.BytesIO(wav_data)) as source:
                audio = recognizer.record(source)
        except Exception as exc:
            logger.warning("Failed to parse audio stream: %s", exc)
            raise AppError("Unable to process audio format. Please provide a standard WAV, WebM, or MP3 recording.") from exc

        locale = LANGUAGE_LOCALE_MAP.get((language or "").lower(), "en-US") if language else "en-US"

        try:
            text = recognizer.recognize_google(audio, language=locale)
            if not text:
                raise AppError("No speech detected in audio. Please speak clearly and try again.")
            return TranscriptionResult(text=text.strip(), language=language, confidence=0.95)
        except sr.UnknownValueError as exc:
            logger.info("Speech recognition: unknown value")
            raise AppError("Unable to recognize speech in audio. Please try again.") from exc
        except sr.RequestError as exc:
            logger.warning("Speech recognition request error: %s", exc)
            raise ProviderError("Voice recognition service is temporarily unavailable. Please try again.") from exc
        except Exception as exc:
            logger.exception("Unexpected STT failure")
            raise ProviderError("Voice recognition is temporarily unavailable.") from exc


class MockSTTProvider(SpeechToTextProvider):
    """Mock STT provider for testing and deterministic offline fallback."""

    def __init__(self, mocked_text: str = "Hello this is a test speech transcription") -> None:
        self.mocked_text = mocked_text

    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes or len(audio_bytes) < 10:
            raise AppError("Audio file is empty or invalid.")
        return TranscriptionResult(
            text=self.mocked_text,
            language=language or "en",
            confidence=0.98,
        )
