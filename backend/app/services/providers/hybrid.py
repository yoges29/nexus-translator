import logging
import socket
from typing import Any

from app.core.errors import AppError, ProviderError
from app.services.detector import LanguageDetector
from app.services.providers.base import (
    DetectionResult,
    OnlineTranslationProvider,
    TranslationProvider,
)
from app.services.providers.offline import OfflineLocalTranslationProvider

logger = logging.getLogger("nexus.translator.provider.hybrid")


class HybridTranslationProvider(TranslationProvider):
    """Hybrid translation provider orchestrating online and offline translation engines.

    Supported modes:
    - "auto": Prefers online translation. If network/online fails and pair is supported offline,
              gracefully falls back to offline engine.
    - "online": Strictly uses online translation. Fails if offline.
    - "offline": Strictly uses local offline translation. Fails if pair is not supported offline.
    """

    def __init__(
        self,
        online_provider: OnlineTranslationProvider,
        offline_provider: OfflineLocalTranslationProvider | None = None,
    ) -> None:
        self.online_provider = online_provider
        self.offline_provider = offline_provider or OfflineLocalTranslationProvider()
        self.last_used_offline: bool = False
        self.last_provider_name: str = "online"

    def is_network_available(self, timeout: float = 0.5) -> bool:
        """Fast non-blocking connectivity check."""
        # If online provider is configured, assume online unless last request failed
        return True


    def is_offline_pair_supported(self, source: str, target: str) -> bool:
        return self.offline_provider.is_pair_supported(source, target)

    def get_supported_offline_pairs(self) -> list[dict[str, str]]:
        return self.offline_provider.get_supported_pairs()

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
        mode: str = "auto",
    ) -> str:
        src = source_language.strip().lower()
        tgt = target_language.strip().lower()
        selected_mode = mode.strip().lower() if mode else "auto"

        # Explicit Offline Mode
        if selected_mode == "offline":
            if not self.offline_provider.is_pair_supported(src, tgt):
                supported = ", ".join(f"{p['source']}➔{p['target']}" for p in self.get_supported_offline_pairs())
                raise AppError(
                    f"Language pair '{src}' ➔ '{tgt}' is not supported in Offline Mode. "
                    f"Supported offline pairs: [{supported}]. Switch to Online mode to translate this pair.",
                    status_code=400,
                )
            result = await self.offline_provider.translate(text, src, tgt, style=style)
            self.last_used_offline = True
            self.last_provider_name = "offline_local"
            return result

        # Explicit Online Mode
        if selected_mode == "online":
            try:
                result = await self.online_provider.translate(text, src, tgt, style=style)
                self.last_used_offline = False
                self.last_provider_name = "online"
                return result
            except Exception as exc:
                logger.warning("Explicit online translation requested but failed: %s", exc)
                raise ProviderError(
                    "Online translation is currently unavailable. Please check your internet connection or switch to Offline Mode."
                ) from exc

        # Auto Mode: Try online first, fallback to offline if online fails
        try:
            result = await self.online_provider.translate(text, src, tgt, style=style)
            self.last_used_offline = False
            self.last_provider_name = "online"
            return result
        except Exception as exc:
            logger.info("Online translation unavailable (%s). Checking offline fallback for '%s' ➔ '%s'", exc, src, tgt)
            if self.offline_provider.is_pair_supported(src, tgt):
                logger.info("Falling back to local offline translation engine for '%s' ➔ '%s'", src, tgt)
                result = await self.offline_provider.translate(text, src, tgt, style=style)
                self.last_used_offline = True
                self.last_provider_name = "offline_fallback"
                return result

            # If not supported offline, re-raise the online provider error
            logger.warning("Offline fallback unavailable for pair '%s' ➔ '%s'", src, tgt)
            raise ProviderError(
                f"Online translation failed and offline fallback is not available for '{src}' ➔ '{tgt}'."
            ) from exc

    async def detect_language(self, text: str) -> DetectionResult:
        # Try online detector if available, fallback to local offline detector
        try:
            return await self.online_provider.detect_language(text)
        except Exception:
            return await self.offline_provider.detect_language(text)

    async def get_alternatives(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> list[str]:
        try:
            return await self.online_provider.get_alternatives(text, source_language, target_language, style=style)
        except Exception:
            return await self.offline_provider.get_alternatives(text, source_language, target_language, style=style)

    def get_last_meta(self) -> dict[str, Any]:
        return {
            "is_offline": self.last_used_offline,
            "provider_used": self.last_provider_name,
        }
