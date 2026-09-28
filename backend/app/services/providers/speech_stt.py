import io
import logging
import os
import shutil
import socket
import subprocess
import tempfile

# Prefer IPv4 resolution to prevent dual-stack IPv6 connection aborts on Windows
_original_getaddrinfo = socket.getaddrinfo


def _ipv4_preferred_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        res = _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        if res:
            return res
    except Exception:
        pass
    return _original_getaddrinfo(host, port, family, type, proto, flags)


socket.getaddrinfo = _ipv4_preferred_getaddrinfo

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


def find_ffmpeg_executable() -> str | None:
    """Find the path to ffmpeg executable on Windows, Linux, or Mac."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import pydub.utils

        exe = pydub.utils.which("ffmpeg")
        if exe:
            return exe
    except Exception:
        pass

    for candidate in [
        r"C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/bin/ffmpeg",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def detect_audio_format(audio_bytes: bytes, content_type: str = "", filename: str | None = None) -> tuple[str, str]:
    """
    Detect the audio container format and recommended file extension.
    Returns: (format_name, file_extension) e.g. ("webm", ".webm")
    """
    header = audio_bytes[:32] if audio_bytes else b""

    # 1. Magic bytes detection
    if header.startswith(b"RIFF") and b"WAVE" in header[:16]:
        return "wav", ".wav"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm", ".webm"
    if header.startswith(b"OggS"):
        return "ogg", ".ogg"
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
        return "mp3", ".mp3"
    if len(header) >= 12 and (b"ftyp" in header[4:12] or b"moov" in header):
        return "mp4", ".mp4"
    if header.startswith(b"fLaC"):
        return "flac", ".flac"

    # 2. Filename extension detection
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".webm", ".mkv"):
            return "webm", ".webm"
        if ext in (".wav", ".wave"):
            return "wav", ".wav"
        if ext in (".mp4", ".m4a", ".aac"):
            return "mp4", ".mp4"
        if ext in (".ogg", ".opus", ".oga"):
            return "ogg", ".ogg"
        if ext == ".mp3":
            return "mp3", ".mp3"
        if ext == ".flac":
            return "flac", ".flac"

    # 3. Content-Type header detection
    ct = (content_type or "").lower()
    if "webm" in ct:
        return "webm", ".webm"
    if "wav" in ct or "wave" in ct:
        return "wav", ".wav"
    if "mp4" in ct or "m4a" in ct or "aac" in ct:
        return "mp4", ".mp4"
    if "ogg" in ct or "opus" in ct:
        return "ogg", ".ogg"
    if "mp3" in ct or "mpeg" in ct:
        return "mp3", ".mp3"
    if "flac" in ct:
        return "flac", ".flac"

    # Default fallback for browser MediaRecorder output
    return "webm", ".webm"


class SpeechRecognitionSTTProvider(SpeechToTextProvider):
    """Speech-to-Text provider utilizing Python speech_recognition with robust audio decoding."""

    def _convert_to_wav_bytes(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        filename: str | None = None,
    ) -> bytes:
        # Check if already a valid RIFF WAV
        if audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]:
            return audio_bytes

        fmt_name, ext = detect_audio_format(audio_bytes, content_type, filename)
        logger.debug("Detected audio format: %s (%s) for conversion", fmt_name, ext)

        # 1. Primary conversion method: Direct ffmpeg subprocess with temporary files.
        # This provides maximum reliability for browser-recorded WebM Opus streams
        # (handling missing durations, unseekable clusters, and arbitrary codecs).
        ffmpeg_exe = find_ffmpeg_executable()
        if ffmpeg_exe:
            in_temp = None
            out_temp = None
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as in_f:
                    in_f.write(audio_bytes)
                    in_temp = in_f.name

                out_temp = in_temp + ".wav"
                cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    in_temp,
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-f",
                    "wav",
                    out_temp,
                ]
                proc = subprocess.run(cmd, capture_output=True, timeout=15)
                if proc.returncode == 0 and os.path.isfile(out_temp):
                    with open(out_temp, "rb") as out_f:
                        wav_data = out_f.read()
                    if wav_data.startswith(b"RIFF") and b"WAVE" in wav_data[:16]:
                        logger.debug("Successfully converted audio using ffmpeg CLI: %d bytes", len(wav_data))
                        return wav_data
                else:
                    logger.warning(
                        "FFmpeg CLI conversion failed (code %s): %s",
                        proc.returncode,
                        proc.stderr.decode(errors="ignore")[:300],
                    )
            except Exception as exc:
                logger.warning("Error running ffmpeg CLI: %s", exc)
            finally:
                if in_temp and os.path.exists(in_temp):
                    try:
                        os.remove(in_temp)
                    except OSError:
                        pass
                if out_temp and os.path.exists(out_temp):
                    try:
                        os.remove(out_temp)
                    except OSError:
                        pass

        # 2. Secondary fallback: pydub AudioSegment
        try:
            from pydub import AudioSegment

            format_hint = fmt_name if fmt_name != "mp4" else "mp4"
            segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=format_hint)
            segment = segment.set_frame_rate(16000).set_channels(1)
            output_io = io.BytesIO()
            segment.export(output_io, format="wav")
            wav_bytes = output_io.getvalue()
            if wav_bytes.startswith(b"RIFF") and b"WAVE" in wav_bytes[:16]:
                logger.debug("Successfully converted audio using pydub: %d bytes", len(wav_bytes))
                return wav_bytes
        except Exception as exc:
            logger.warning("pydub conversion fallback failed: %s", exc)

        # If audio_bytes is already PCM or raw, return as is
        return audio_bytes

    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        filename: str | None = None,
        language: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes or len(audio_bytes) < 32:
            raise AppError("Audio file is empty or invalid.")

        import speech_recognition as sr

        wav_data = self._convert_to_wav_bytes(audio_bytes, content_type, filename)
        recognizer = sr.Recognizer()

        try:
            with sr.AudioFile(io.BytesIO(wav_data)) as source:
                audio = recognizer.record(source)
        except Exception as exc:
            logger.warning("Failed to parse audio stream: %s", exc)
            raise AppError(
                "Unable to process audio format. Please provide a standard WAV, WebM, or MP3 recording."
            ) from exc

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
        filename: str | None = None,
        language: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes or len(audio_bytes) < 10:
            raise AppError("Audio file is empty or invalid.")
        return TranscriptionResult(
            text=self.mocked_text,
            language=language or "en",
            confidence=0.98,
        )
