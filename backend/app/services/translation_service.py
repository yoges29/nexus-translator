import asyncio
import inspect
import logging
from typing import Any

from sqlalchemy.orm import Session


from app.core.config import get_settings
from app.core.errors import AppError, ProviderError
from app.core.languages import get_language_by_code, is_translation_supported
from app.models.translation import TranslationHistory
from app.services.detector import LanguageDetector
from app.services.linguistic_adapter import LinguisticAdapter
from app.services.multilingual_engine import MultilingualEngine
from app.services.provider_factory import (
    get_ocr_provider,
    get_stt_provider,
    get_translation_provider,
    get_tts_provider,
)
from app.services.providers.base import SynthesisResult, TranscriptionResult

logger = logging.getLogger("nexus.translator.service")


class TranslationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.provider = get_translation_provider()
        self.stt_provider = get_stt_provider()
        self.tts_provider = get_tts_provider()
        self.ocr_provider = get_ocr_provider()

    def _validate_text(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            raise AppError("Text cannot be empty.")
        if len(cleaned) > self.settings.max_text_length:
            raise AppError(f"Text exceeds maximum length of {self.settings.max_text_length} characters.")
        return cleaned

    def _validate_languages(self, source: str, target: str) -> tuple[str, str]:
        source_code = source.strip().lower()
        target_code = target.strip().lower()

        if source_code != "auto" and not is_translation_supported(source_code):
            raise AppError(f"Unsupported source language: {source_code}")
        if not is_translation_supported(target_code):
            raise AppError(f"Unsupported target language: {target_code}")
        if source_code == target_code:
            raise AppError("Source and target languages must be different.")
        return source_code, target_code

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
        input_method: str = "text",
        user_id: int | None = None,
        mode: str = "auto",
    ) -> tuple[str, str, str, str, str, str | None, int | None]:
        cleaned = self._validate_text(text)
        source_code, target_code = self._validate_languages(source_language, target_language)

        # 1. Check in-memory translation cache for repeated requests
        from app.services.cache import translation_cache
        cache_key = translation_cache.make_translation_key(cleaned, source_code, target_code, style, mode)
        cached_result = translation_cache.get(cache_key)
        if cached_result is not None:
            translated, detected_lang, meta_dict = cached_result
            self._cached_meta = meta_dict
            resolved_source = source_code if source_code != "auto" else (detected_lang or "auto")

            # Fast history persistence
            hist_id: int | None = None
            try:
                record = TranslationHistory(
                    user_id=user_id,
                    source_language=resolved_source,
                    target_language=target_code,
                    original_text=cleaned,
                    translated_text=translated,
                    detected_language=detected_lang,
                    translation_style=style,
                    input_method=input_method,
                )
                self.db.add(record)
                self.db.commit()
                hist_id = record.id
            except Exception as exc:
                logger.warning("History save failed on cache hit: %s", exc)
                self.db.rollback()

            return (
                resolved_source,
                target_code,
                translated,
                style,
                input_method,
                detected_lang,
                hist_id,
            )

        resolved_source = source_code
        detected_lang = None

        # 2. Language Detection: Fast path
        # If user explicitly selected source language, do not perform auto detection
        if source_code != "auto":
            resolved_source = source_code
            detected_lang = None
            # Check mixed only if non-Latin scripts are present
            is_mixed = MultilingualEngine.get_script(cleaned) != "latin" and MultilingualEngine.is_multilingual(cleaned)
        else:
            is_mixed = MultilingualEngine.is_multilingual(cleaned)

        if is_mixed:
            if source_code == "auto":
                det_code = MultilingualEngine.detect_segment_language(cleaned)
                detected_lang = det_code if det_code != "auto" else "mixed"
                resolved_source = "auto"

            try:
                sig = inspect.signature(self.provider.translate)
                extra_opts: dict[str, Any] = {}
                if "mode" in sig.parameters:
                    extra_opts["mode"] = mode

                async def do_translate(seg_text: str, seg_src: str, seg_tgt: str, **kw: Any) -> str:
                    if seg_src == seg_tgt and seg_src != "auto":
                        return seg_text
                    return await self.provider.translate(seg_text, seg_src, seg_tgt, **kw)

                translated = await MultilingualEngine.translate_multilingual(
                    cleaned, target_code, do_translate, style=style, **extra_opts
                )
            except (AppError, ProviderError):
                raise
            except Exception as exc:
                logger.exception("Unexpected multilingual translation failure")
                raise ProviderError() from exc
        else:
            if source_code == "auto":
                # High-speed local detection first
                fast_det = LanguageDetector.detect(cleaned[:400])
                if (
                    fast_det
                    and fast_det.language
                    and is_translation_supported(fast_det.language)
                    and fast_det.language != target_code
                ):
                    resolved_source = fast_det.language
                    detected_lang = resolved_source
                else:
                    detection = await self.provider.detect_language(cleaned[:1000])
                    resolved_source = detection.language
                    detected_lang = resolved_source
                    if resolved_source == target_code:
                        alt_detection = LanguageDetector.detect(cleaned[:1000], exclude_language=target_code)
                        if (
                            alt_detection
                            and alt_detection.language != target_code
                            and is_translation_supported(alt_detection.language)
                        ):
                            resolved_source = alt_detection.language
                            detected_lang = resolved_source
                        else:
                            raise AppError("Source and target languages must be different.")
                    elif not is_translation_supported(resolved_source):
                        raise AppError(f"Detected language is not supported: {resolved_source}")

            try:
                sig = inspect.signature(self.provider.translate)
                kwargs = {"style": style}
                if "mode" in sig.parameters:
                    kwargs["mode"] = mode

                # Chunk only when necessary (<= 2500 chars fits safely in single request)
                if len(cleaned) <= 2500:
                    translated = await self.provider.translate(
                        cleaned, resolved_source, target_code, **kwargs
                    )
                else:
                    chunks = MultilingualEngine.smart_chunk_text(cleaned, max_chunk_size=2500)
                    sem = asyncio.Semaphore(5)

                    async def _trans_chunk(chunk_str: str) -> str:
                        if not chunk_str.strip():
                            return chunk_str
                        async with sem:
                            return await self.provider.translate(
                                chunk_str, resolved_source, target_code, **kwargs
                            )

                    translated_chunks = await asyncio.gather(*[_trans_chunk(c) for c in chunks])
                    translated = "".join(translated_chunks)
            except (AppError, ProviderError):
                raise
            except Exception as exc:
                logger.exception("Unexpected translation failure")
                raise ProviderError() from exc

        # Cache the successful translation
        meta = self.get_last_translation_meta()
        translation_cache.set(cache_key, (translated, detected_lang, meta))

        # Save history without redundant refresh query
        hist_id = None
        try:
            record = TranslationHistory(
                user_id=user_id,
                source_language=resolved_source,
                target_language=target_code,
                original_text=cleaned,
                translated_text=translated,
                detected_language=detected_lang,
                translation_style=style,
                input_method=input_method,
            )
            self.db.add(record)
            self.db.commit()
            hist_id = record.id
        except Exception as exc:
            logger.warning("History save failed: %s", exc)
            self.db.rollback()

        return (
            resolved_source,
            target_code,
            translated,
            style,
            input_method,
            detected_lang,
            hist_id,
        )

    def get_last_translation_meta(self) -> dict[str, Any]:
        if hasattr(self, "_cached_meta") and self._cached_meta:
            return self._cached_meta

        meta_func = getattr(self.provider, "get_last_meta", None)
        if callable(meta_func):
            try:
                res = meta_func()
                if isinstance(res, dict):
                    return {
                        "is_offline": bool(res.get("is_offline", False)),
                        "provider_used": str(res.get("provider_used", "online")),
                    }
            except Exception:
                pass

        is_off = bool(getattr(self.provider, "is_offline", False) is True)
        return {
            "is_offline": is_off,
            "provider_used": "offline_local" if is_off else "online",
        }


    def get_offline_status(self) -> dict[str, Any]:
        if hasattr(self.provider, "get_supported_offline_pairs"):
            pairs = self.provider.get_supported_offline_pairs()
            online_avail = getattr(self.provider, "is_network_available", lambda: True)()
        elif hasattr(self.provider, "get_supported_pairs"):
            pairs = self.provider.get_supported_pairs()
            online_avail = False
        else:
            from app.services.providers.offline import OfflineLocalTranslationProvider
            off = OfflineLocalTranslationProvider()
            pairs = off.get_supported_pairs()
            online_avail = True

        return {
            "online_available": online_avail,
            "current_mode": "auto",
            "supported_pairs": pairs,
        }


    async def get_alternatives(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> tuple[str, list[str]]:
        cleaned = self._validate_text(text)
        source_code, target_code = self._validate_languages(source_language, target_language)

        resolved_source = source_code
        if MultilingualEngine.is_multilingual(cleaned):
            if source_code == "auto":
                resolved_source = "auto"
            try:
                async def do_translate(seg_text: str, seg_src: str, seg_tgt: str, **kw: Any) -> str:
                    if seg_src == seg_tgt and seg_src != "auto":
                        return seg_text
                    return await self.provider.translate(seg_text, seg_src, seg_tgt, **kw)

                primary = await MultilingualEngine.translate_multilingual(
                    cleaned, target_code, do_translate, style=style
                )
                alternatives = await self.provider.get_alternatives(
                    primary, target_code, target_code, style=style
                )
                if not alternatives:
                    alternatives = LinguisticAdapter.generate_alternatives(
                        primary, target_code, target_code, style=style
                    )
                return primary, alternatives
            except ProviderError:
                raise
            except Exception as exc:
                logger.exception("Unexpected alternatives failure in multilingual mode")
                raise ProviderError() from exc

        if len(cleaned) > 1000:
            primary = (
                await self.translate(
                    cleaned,
                    source_language=source_code,
                    target_language=target_code,
                    style=style,
                )
            )[2]
            return primary, []

        if source_code == "auto":
            detection = await self.provider.detect_language(cleaned[:1000])
            resolved_source = detection.language
            if not is_translation_supported(resolved_source):
                raise AppError(f"Detected language is not supported: {resolved_source}")
            if resolved_source == target_code:
                raise AppError("Source and target languages must be different.")

        # Check translation cache first to avoid re-translating
        from app.services.cache import translation_cache
        cache_key = translation_cache.make_translation_key(cleaned, source_code, target_code, style, "auto")
        cached = translation_cache.get(cache_key)
        if cached is not None:
            primary = cached[0]
            alternatives = LinguisticAdapter.generate_alternatives(
                primary, resolved_source, target_code, style=style
            )
            return primary, alternatives

        try:
            primary = await self.provider.translate(
                cleaned, resolved_source, target_code, style=style
            )
            alternatives = await self.provider.get_alternatives(
                cleaned, resolved_source, target_code, style=style
            )
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("Unexpected alternatives failure")
            raise ProviderError() from exc

        return primary, alternatives

    async def detect_language(self, text: str) -> tuple[str, float | None]:
        cleaned = self._validate_text(text)
        try:
            result = await self.provider.detect_language(cleaned[:1000])
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("Unexpected detection failure")
            raise ProviderError() from exc

        language = result.language
        if not get_language_by_code(language):
            logger.info("Detected language %s is outside registry", language)
        return language, result.confidence

    async def transcribe_speech(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes:
            raise AppError("Audio payload cannot be empty.")
        if len(audio_bytes) > self.settings.max_audio_size_bytes:
            raise AppError("Audio file exceeds maximum allowed size.")
        return await self.stt_provider.transcribe(
            audio_bytes, content_type=content_type, language=language
        )

    async def synthesize_speech(
        self,
        text: str,
        language: str,
        speed: float = 1.0,
        voice: str | None = None,
    ) -> SynthesisResult:
        cleaned = self._validate_text(text)
        if not is_translation_supported(language):
            raise AppError(f"Language '{language}' is not supported for voice synthesis.")
        return await self.tts_provider.synthesize(
            cleaned, language=language, speed=speed, voice=voice
        )

    def _validate_image_bytes(self, image_bytes: bytes, filename: str = "", content_type: str = "") -> None:
        if not image_bytes:
            raise AppError("Image payload cannot be empty.")
        if len(image_bytes) > self.settings.max_image_size_bytes:
            max_mb = self.settings.max_image_size_bytes // (1024 * 1024)
            raise AppError(f"Image exceeds maximum allowed size of {max_mb}MB.", status_code=413)

        # Validate MIME and extension if present
        allowed_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        allowed_mimes = {"image/png", "image/jpeg", "image/jpg", "image/webp", "application/octet-stream"}

        if filename:
            from pathlib import Path
            ext = Path(filename).suffix.lower()
            if ext and ext not in allowed_extensions:
                raise AppError(f"Unsupported image format '{ext}'. Allowed formats: PNG, JPG, JPEG, WEBP.")

        if content_type and content_type.lower() not in allowed_mimes:
            raise AppError(f"Unsupported image MIME type '{content_type}'. Allowed types: PNG, JPEG, WEBP.")

    async def extract_ocr(
        self,
        image_bytes: bytes,
        filename: str = "",
        content_type: str = "",
    ) -> dict:
        self._validate_image_bytes(image_bytes, filename=filename, content_type=content_type)
        try:
            raw_res = self.ocr_provider.process_image(image_bytes)
            if inspect.isawaitable(raw_res):
                ocr_res = await raw_res
            else:
                ocr_res = raw_res
        except AppError:
            raise
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("OCR extraction failure: %s", exc)
            raise ProviderError("Failed to extract text from image.") from exc

        detected_lang = ocr_res.language
        if not detected_lang and ocr_res.text.strip():
            det = LanguageDetector.detect(ocr_res.text.strip()[:300])
            detected_lang = det.language

        return {
            "text": ocr_res.text,
            "language": detected_lang,
            "regions": [r.to_dict() for r in ocr_res.regions],
        }

    async def translate_image(
        self,
        image_bytes: bytes,
        target_language: str,
        source_language: str = "auto",
        translation_style: str = "general",
        filename: str = "",
        content_type: str = "",
        user_id: int | None = None,
    ) -> dict:
        ocr_data = await self.extract_ocr(image_bytes, filename=filename, content_type=content_type)
        extracted_text = ocr_data["text"].strip()
        if not extracted_text:
            raise AppError("No text was detected in the uploaded image. Please ensure the image contains legible text.")

        target_code = target_language.strip().lower()
        source_code = source_language.strip().lower()

        if not is_translation_supported(target_code):
            raise AppError(f"Unsupported target language: {target_code}")

        resolved_source = source_code
        if resolved_source == "auto":
            resolved_source = ocr_data.get("language") or "en"
            if not is_translation_supported(resolved_source):
                det = LanguageDetector.detect(extracted_text[:300])
                resolved_source = det.language
                if not is_translation_supported(resolved_source):
                    resolved_source = "en"

        if resolved_source == target_code:
            raise AppError("Source and target languages must be different.")

        try:
            translated = await self.provider.translate(
                extracted_text, resolved_source, target_code, style=translation_style
            )
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("Image translation failure: %s", exc)
            raise ProviderError("Failed to translate image text.") from exc

        from app.models.translation import TranslationHistory
        record = TranslationHistory(
            user_id=user_id,
            source_language=resolved_source,
            target_language=target_code,
            original_text=extracted_text,
            translated_text=translated,
            detected_language=resolved_source if source_code == "auto" else None,
            translation_style=translation_style,
            input_method="image",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        # Populate translated_text on each detected bounding box region for AR overlay
        regions = ocr_data.get("regions", [])
        for region in regions:
            reg_text = region.get("text", "").strip()
            if reg_text:
                try:
                    res = self.provider.translate(reg_text, resolved_source, target_code, style=translation_style)
                    if inspect.isawaitable(res):
                        res = await res
                    region["translated_text"] = str(res)
                except Exception:
                    region["translated_text"] = None
            else:
                region["translated_text"] = None

        return {
            "source_language": resolved_source,
            "target_language": target_code,
            "extracted_text": extracted_text,
            "translated_text": translated,
            "detected_language": resolved_source,
            "translation_style": translation_style,
            "regions": regions,
            "history_id": record.id,
        }


    def list_history(
        self,
        input_method: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TranslationHistory], int]:
        from app.models.translation import TranslationHistory
        from sqlalchemy import or_

        query = self.db.query(TranslationHistory)
        if input_method and input_method.lower() != "all":
            query = query.filter(TranslationHistory.input_method == input_method.lower())
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    TranslationHistory.original_text.ilike(term),
                    TranslationHistory.translated_text.ilike(term),
                    TranslationHistory.source_language.ilike(term),
                    TranslationHistory.target_language.ilike(term),
                )
            )

        total = query.count()
        items = (
            query.order_by(TranslationHistory.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def delete_history(self, history_id: int) -> None:
        from app.models.translation import TranslationHistory
        record = self.db.get(TranslationHistory, history_id)
        if not record:
            raise AppError("History item not found.", status_code=404)
        self.db.delete(record)
        self.db.commit()


