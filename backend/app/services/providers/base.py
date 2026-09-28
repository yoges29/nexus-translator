from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DetectionResult:
    language: str
    confidence: float | None = None


@dataclass
class TranscriptionResult:
    text: str
    language: str | None = None
    confidence: float | None = None


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    content_type: str = "audio/mpeg"
    format: str = "mp3"


class TranslationProvider(ABC):
    @abstractmethod
    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def detect_language(self, text: str) -> DetectionResult:
        raise NotImplementedError

    @abstractmethod
    async def get_alternatives(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> list[str]:
        raise NotImplementedError


class OnlineTranslationProvider(TranslationProvider):
    """Base class for remote / cloud translation providers."""

    is_offline: bool = False


class OfflineTranslationProvider(TranslationProvider):
    """Base class for local / offline translation engines."""

    is_offline: bool = True

    @abstractmethod
    def is_pair_supported(self, source_language: str, target_language: str) -> bool:
        """Check if this language pair is supported offline."""
        raise NotImplementedError

    @abstractmethod
    def get_supported_pairs(self) -> list[dict[str, str]]:
        """Return list of supported offline language pairs."""
        raise NotImplementedError



class SpeechToTextProvider(ABC):
    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        filename: str | None = None,
        language: str | None = None,
    ) -> TranscriptionResult:
        raise NotImplementedError


class TextToSpeechProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str,
        speed: float = 1.0,
        voice: str | None = None,
    ) -> SynthesisResult:
        raise NotImplementedError
