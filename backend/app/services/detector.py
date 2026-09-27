import logging
import re
from dataclasses import dataclass

from app.core.languages import get_language_by_code

logger = logging.getLogger("nexus.translator.detector")

# Unicode script ranges for supported non-Latin languages
SCRIPT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ta", re.compile(r"[\u0B80-\u0BFF]")),  # Tamil
    ("hi", re.compile(r"[\u0900-\u097F]")),  # Hindi / Devanagari
    ("te", re.compile(r"[\u0C00-\u0C7F]")),  # Telugu
    ("ml", re.compile(r"[\u0D00-\u0D7F]")),  # Malayalam
    ("kn", re.compile(r"[\u0C80-\u0CFF]")),  # Kannada
    ("ja", re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")),  # Japanese Kana
    ("ko", re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]")),  # Korean Hangul
    ("ar", re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")),  # Arabic
    ("zh", re.compile(r"[\u4E00-\u9FFF]")),  # Chinese Hanzi (when no Kana present)
]


@dataclass
class DetectionResult:
    language: str
    confidence: float | None = None


class LanguageDetector:
    """Real multi-tier language detector using script block analysis, langdetect, and provider fallbacks."""

    @classmethod
    def detect(cls, text: str, exclude_language: str | None = None) -> DetectionResult:
        cleaned = text.strip()
        if not cleaned:
            return DetectionResult(language="en", confidence=None)

        # Check cache if no exclusion
        cache_key = None
        if not exclude_language:
            from app.services.cache import detection_cache
            cache_key = detection_cache.make_detection_key(cleaned)
            cached = detection_cache.get(cache_key)
            if cached is not None:
                return cached

        if exclude_language:
            for lang_code, pattern in SCRIPT_PATTERNS:
                if lang_code == exclude_language:
                    cleaned = pattern.sub("", cleaned).strip()
                    break
            if not cleaned:
                return DetectionResult(language="en", confidence=None)

        sample = cleaned[:400]

        # 1. High-precision Unicode Script Analysis (ultra-fast regex)
        total_chars = len(re.sub(r"\s+", "", sample))
        if total_chars > 0:
            for lang_code, pattern in SCRIPT_PATTERNS:
                matches = pattern.findall(sample)
                if matches:
                    ratio = len(matches) / total_chars
                    if ratio >= 0.20:  # Significant script representation
                        confidence = round(min(ratio * 1.2, 1.0), 2)
                        res = DetectionResult(language=lang_code, confidence=confidence)
                        if cache_key:
                            from app.services.cache import detection_cache
                            detection_cache.set(cache_key, res)
                        return res

        # Fast path: Plain ASCII text with standard English characters
        if re.match(r"^[a-zA-Z0-9\s.,!?'\"()–—:;\-/]+$", sample) and len(sample) > 3:
            res = DetectionResult(language="en", confidence=0.95)
            if cache_key:
                from app.services.cache import detection_cache
                detection_cache.set(cache_key, res)
            return res

        # 2. Latin & General Language Detection using langdetect on sample
        try:
            from langdetect import detect_langs

            detected = detect_langs(sample)
            if detected:
                # Prioritize candidates supported by our registry
                for candidate in detected:
                    cand_code = candidate.lang.lower()
                    if cand_code.startswith("zh"):
                        cand_code = "zh"
                    if get_language_by_code(cand_code):
                        res = DetectionResult(language=cand_code, confidence=round(float(candidate.prob), 2))
                        if cache_key:
                            from app.services.cache import detection_cache
                            detection_cache.set(cache_key, res)
                        return res

                # If detected language is outside registry, but Latin alphabet is present, fallback to English
                if re.search(r"[a-zA-Z]", sample) and get_language_by_code("en"):
                    res = DetectionResult(language="en", confidence=0.8)
                    if cache_key:
                        from app.services.cache import detection_cache
                        detection_cache.set(cache_key, res)
                    return res

                best = detected[0]
                lang_code = best.lang.lower()
                conf = round(float(best.prob), 2)

                # Normalize Chinese variants
                if lang_code.startswith("zh"):
                    lang_code = "zh"

                res = DetectionResult(language=lang_code, confidence=conf)
                if cache_key:
                    from app.services.cache import detection_cache
                    detection_cache.set(cache_key, res)
                return res
        except Exception as exc:
            logger.debug("langdetect exception: %s", exc)

        # 3. Default fallback for plain ASCII Latin text
        if re.search(r"[a-zA-Z]", sample):
            res = DetectionResult(language="en", confidence=0.85)
        else:
            res = DetectionResult(language="en", confidence=None)

        if cache_key:
            from app.services.cache import detection_cache
            detection_cache.set(cache_key, res)
        return res
