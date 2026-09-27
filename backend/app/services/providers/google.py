import logging

from app.core.config import get_settings
from app.core.errors import ProviderError
from app.services.detector import LanguageDetector
from app.services.linguistic_adapter import LinguisticAdapter
from app.services.providers.base import DetectionResult, OnlineTranslationProvider

logger = logging.getLogger("nexus.translator.provider.google")


class GoogleTranslateProvider(OnlineTranslationProvider):

    """Google Cloud Translation API v2 provider."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _client(self):
        try:
            from google.cloud import translate_v2 as translate
        except ImportError as exc:
            raise ProviderError(
                "Google Cloud Translate library is not installed. Add google-cloud-translate to requirements."
            ) from exc

        if self.settings.google_application_credentials:
            import os

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.settings.google_application_credentials
        return translate.Client()

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> str:
        client = self._client()
        try:
            result = client.translate(
                text,
                source_language=source_language,
                target_language=target_language,
                format_="text",
            )
        except Exception as exc:
            logger.warning("Google translate failed: %s", exc.__class__.__name__)
            raise ProviderError() from exc
        translated = result.get("translatedText")
        if not translated:
            raise ProviderError()
        raw_translated = str(translated)
        if style != "general":
            return LinguisticAdapter.apply_style(raw_translated, target_language, style)
        return raw_translated

    async def detect_language(self, text: str) -> DetectionResult:
        try:
            client = self._client()
            result = client.detect_language(text)
            language = str(result.get("language", "")).lower()
            confidence_raw = result.get("confidence")
            confidence = float(confidence_raw) if confidence_raw is not None else None
            if language:
                return DetectionResult(language=language, confidence=confidence)
        except Exception as exc:
            logger.warning("Google detect failed: %s, falling back to local detector", exc.__class__.__name__)
        return LanguageDetector.detect(text)

    async def get_alternatives(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> list[str]:
        primary = await self.translate(text, source_language, target_language, style=style)
        return LinguisticAdapter.generate_alternatives(
            primary, source_language, target_language, style=style
        )

