from functools import lru_cache

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.providers.base import (
    SpeechToTextProvider,
    TextToSpeechProvider,
    TranslationProvider,
)
from app.services.providers.google import GoogleTranslateProvider
from app.services.providers.libretranslate import LibreTranslateProvider
from app.services.providers.speech_stt import (
    MockSTTProvider,
    SpeechRecognitionSTTProvider,
)
from app.services.providers.ocr import (
    CloudVisionOCRProvider,
    MockOCRProvider,
    OCRProvider,
    RapidOCRProvider,
    TesseractOCRProvider,
)
from app.services.providers.speech_tts import (
    GTTSTextToSpeechProvider,
    MockTTSProvider,
)


from app.services.providers.hybrid import HybridTranslationProvider
from app.services.providers.offline import OfflineLocalTranslationProvider


@lru_cache
def get_translation_provider() -> TranslationProvider:
    settings = get_settings()
    provider_name = settings.translation_provider.strip().lower()
    if provider_name == "google":
        online = GoogleTranslateProvider()
    elif provider_name == "libretranslate":
        online = LibreTranslateProvider()
    elif provider_name == "offline":
        return OfflineLocalTranslationProvider()
    else:
        raise AppError(f"Unsupported translation provider: {provider_name}", status_code=500)

    offline = OfflineLocalTranslationProvider()
    return HybridTranslationProvider(online_provider=online, offline_provider=offline)



@lru_cache
def get_stt_provider() -> SpeechToTextProvider:
    settings = get_settings()
    provider_name = settings.stt_provider.strip().lower()
    if provider_name == "speech_recognition" or provider_name == "google":
        return SpeechRecognitionSTTProvider()
    if provider_name == "mock":
        return MockSTTProvider()
    return SpeechRecognitionSTTProvider()


@lru_cache
def get_tts_provider() -> TextToSpeechProvider:
    settings = get_settings()
    provider_name = settings.tts_provider.strip().lower()
    if provider_name == "gtts" or provider_name == "google":
        return GTTSTextToSpeechProvider()
    if provider_name == "mock":
        return MockTTSProvider()
    return GTTSTextToSpeechProvider()


@lru_cache
def get_ocr_provider() -> OCRProvider:
    settings = get_settings()
    provider_name = settings.ocr_provider.strip().lower()
    if provider_name == "rapidocr":
        return RapidOCRProvider()
    if provider_name == "tesseract":
        return TesseractOCRProvider(tesseract_cmd=settings.tesseract_cmd)
    if provider_name in ("cloud_vision", "google"):
        return CloudVisionOCRProvider(api_key=settings.cloud_vision_api_key)
    if provider_name == "mock":
        return MockOCRProvider()
    # Default to RapidOCR
    return RapidOCRProvider()

