import logging

import httpx

from app.core.config import get_settings
from app.core.errors import ProviderError
from app.services.detector import LanguageDetector
from app.services.linguistic_adapter import LinguisticAdapter
from app.services.providers.base import DetectionResult, OnlineTranslationProvider

logger = logging.getLogger("nexus.translator.provider.libretranslate")


class LibreTranslateProvider(OnlineTranslationProvider):

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.translation_api_url.rstrip("/")
        self.api_key = self.settings.translation_api_key
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            transport = httpx.AsyncHTTPTransport(retries=1, verify=True)
            self._client = httpx.AsyncClient(
                transport=transport,
                timeout=httpx.Timeout(self.settings.translation_timeout_seconds, connect=2.5),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
        return self._client

    async def _close_client(self) -> None:
        if self._client is not None and not self._client.is_closed:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "Accept": "application/json"}

    def _payload_base(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.api_key:
            payload["api_key"] = self.api_key
        return payload

    async def _fallback_translate(self, text: str, source_language: str, target_language: str) -> str | None:
        import urllib.parse
        endpoints = [
            f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_language}&tl={target_language}&dt=t&q={urllib.parse.quote(text)}",
            f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={source_language}&tl={target_language}&q={urllib.parse.quote(text)}",
        ]
        client = self._get_client()
        for url in endpoints:
            try:
                try:
                    res = await client.get(url)
                except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ConnectTimeout):
                    await self._close_client()
                    client = self._get_client()
                    res = await client.get(url)

                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and data:
                        if isinstance(data[0], list):
                            parts = [str(part[0]) for part in data[0] if isinstance(part, list) and part]
                            if parts:
                                return "".join(parts)
                        elif isinstance(data[0], str):
                            return data[0]
                        return str(data[0])
            except Exception as exc:
                logger.debug("Fallback endpoint attempt failed: %s", exc)
                continue
        return None

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> str:
        if not self.api_key and "libretranslate.com" in self.base_url:
            fallback = await self._fallback_translate(text, source_language, target_language)
            if fallback:
                if style != "general":
                    return LinguisticAdapter.apply_style(fallback, target_language, style)
                return fallback
            raise ProviderError(
                "Translation API key is not configured. Set TRANSLATION_API_KEY in your environment."
            )

        payload = {
            **self._payload_base(),
            "q": text,
            "source": source_language,
            "target": target_language,
            "format": "text",
        }

        try:
            client = self._get_client()
            try:
                response = await client.post(
                    f"{self.base_url}/translate",
                    json=payload,
                    headers=self._headers(),
                )
            except (httpx.RemoteProtocolError, httpx.ConnectError):
                await self._close_client()
                client = self._get_client()
                response = await client.post(
                    f"{self.base_url}/translate",
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.TimeoutException as exc:
            logger.warning("LibreTranslate translate timeout")
            fallback = await self._fallback_translate(text, source_language, target_language)
            if fallback:
                if style != "general":
                    return LinguisticAdapter.apply_style(fallback, target_language, style)
                return fallback
            raise ProviderError("Translation request timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            logger.warning("LibreTranslate translate network error: %s", exc.__class__.__name__)
            fallback = await self._fallback_translate(text, source_language, target_language)
            if fallback:
                if style != "general":
                    return LinguisticAdapter.apply_style(fallback, target_language, style)
                return fallback
            raise ProviderError() from exc

        if response.status_code >= 400:
            logger.warning("LibreTranslate translate failed with status %s", response.status_code)
            fallback = await self._fallback_translate(text, source_language, target_language)
            if fallback:
                if style != "general":
                    return LinguisticAdapter.apply_style(fallback, target_language, style)
                return fallback
            raise ProviderError()

        data = response.json()
        translated = data.get("translatedText")
        if not translated:
            fallback = await self._fallback_translate(text, source_language, target_language)
            if fallback:
                if style != "general":
                    return LinguisticAdapter.apply_style(fallback, target_language, style)
                return fallback
            raise ProviderError()

        raw_translated = str(translated)
        if style != "general":
            return LinguisticAdapter.apply_style(raw_translated, target_language, style)
        return raw_translated

    async def detect_language(self, text: str) -> DetectionResult:
        # If API key is present and custom instance configured, attempt remote detection
        if self.api_key or "libretranslate.com" not in self.base_url:
            payload = {**self._payload_base(), "q": text}
            try:
                client = self._get_client()
                response = await client.post(
                    f"{self.base_url}/detect",
                    json=payload,
                    headers=self._headers(),
                )
                if response.status_code == 200:
                    data = response.json()
                    if data and isinstance(data, list):
                        best = data[0]
                        language = str(best.get("language", "")).lower()
                        confidence_raw = best.get("confidence")
                        confidence = float(confidence_raw) if confidence_raw is not None else None
                        if language:
                            return DetectionResult(language=language, confidence=confidence)
            except Exception as exc:
                logger.debug("LibreTranslate remote detect fallback: %s", exc)

        # High-precision local multi-tier detection (Script analysis + langdetect)
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

