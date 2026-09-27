import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.detector import LanguageDetector
from app.services.linguistic_adapter import LinguisticAdapter

logger = logging.getLogger("nexus.translator.multilingual")

# Common expressions mapped to language
KNOWN_EXPRESSIONS: dict[str, str] = {
    # Thanks
    "gracias": "es",
    "muchas gracias": "es",
    "danke": "de",
    "vielen dank": "de",
    "danke schön": "de",
    "merci": "fr",
    "merci beaucoup": "fr",
    "arigato": "ja",
    "arigatou": "ja",
    "ありがとう": "ja",
    "ありがとうございます": "ja",
    "dhanyavaad": "hi",
    "धन्यवाद": "hi",
    "shukriya": "hi",
    "शुक्रिया": "hi",
    "nandri": "ta",
    "நன்றி": "ta",
    "mikka nandri": "ta",
    "மிக்க நன்றி": "ta",
    "thank you": "en",
    "thanks": "en",
    "cheers": "en",
    "grazie": "it",
    "obrigado": "pt",
    "shukran": "ar",
    "شكرا": "ar",
    # Greetings
    "hola": "es",
    "buenos días": "es",
    "buenas tardes": "es",
    "hallo": "de",
    "guten tag": "de",
    "guten morgen": "de",
    "bonjour": "fr",
    "salut": "fr",
    "bon après-midi": "fr",
    "konnichiwa": "ja",
    "こんにちは": "ja",
    "ohayo": "ja",
    "おはよう": "ja",
    "namaste": "hi",
    "नमस्ते": "hi",
    "vanakkam": "ta",
    "வணக்கம்": "ta",
    "kaalai vanakkam": "ta",
    "காலை வணக்கம்": "ta",
    "hello": "en",
    "hi": "en",
    "good morning": "en",
    "good day": "en",
}

# Regex to detect URLs, numbers, emojis
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"^\d+([.,]\d+)?%?$")
EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)


class MultilingualEngine:
    """Unified engine to detect, segment, and translate multi-language mixed inputs

    into 100% pure target-language outputs.
    """

    @staticmethod
    def get_script(text: str) -> str:
        """Identify non-Latin or Latin script family."""
        if re.search(r"[\u0B80-\u0BFF]", text):
            return "ta"
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"
        if re.search(r"[\u3040-\u30FF\u4E00-\u9FFF]", text):
            return "ja"
        if re.search(r"[\u0600-\u06FF]", text):
            return "ar"
        if re.search(r"[\u0C00-\u0C7F]", text):
            return "te"
        if re.search(r"[\u0D00-\u0D7F]", text):
            return "ml"
        if re.search(r"[\u0C80-\u0CFF]", text):
            return "kn"
        if re.search(r"[\uAC00-\uD7AF]", text):
            return "ko"
        if re.search(r"[a-zA-Z\u00C0-\u024F]", text):
            return "latin"
        return "other"

    @staticmethod
    def smart_chunk_text(text: str, max_chunk_size: int = 1500) -> list[str]:
        """Splits text into chunks <= max_chunk_size, preserving paragraph and sentence boundaries."""
        if len(text) <= max_chunk_size:
            return [text]

        chunks: list[str] = []
        paragraphs = re.split(r"(\n+)", text)
        current_chunk: list[str] = []
        current_len = 0

        for part in paragraphs:
            if not part:
                continue
            if len(part) > max_chunk_size:
                if current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_len = 0

                sentences = re.split(r"([.!?。！？]+(?:\s+|$))", part)
                sent_chunk: list[str] = []
                sent_len = 0
                for s in sentences:
                    if not s:
                        continue
                    if sent_len + len(s) > max_chunk_size and sent_chunk:
                        chunks.append("".join(sent_chunk))
                        sent_chunk = []
                        sent_len = 0

                    if len(s) > max_chunk_size:
                        words = re.split(r"(\s+)", s)
                        word_chunk: list[str] = []
                        word_len = 0
                        for w in words:
                            if word_len + len(w) > max_chunk_size and word_chunk:
                                chunks.append("".join(word_chunk))
                                word_chunk = []
                                word_len = 0
                            word_chunk.append(w)
                            word_len += len(w)
                        if word_chunk:
                            sent_chunk.append("".join(word_chunk))
                            sent_len += word_len
                    else:
                        sent_chunk.append(s)
                        sent_len += len(s)

                if sent_chunk:
                    chunks.append("".join(sent_chunk))

            elif current_len + len(part) > max_chunk_size:
                chunks.append("".join(current_chunk))
                current_chunk = [part]
                current_len = len(part)
            else:
                current_chunk.append(part)
                current_len += len(part)

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    @classmethod
    def is_multilingual(cls, text: str) -> bool:
        """Determines if the text contains multiple languages or multiple distinct scripts."""
        cleaned = text.strip()
        if not cleaned:
            return False

        # 1. Check distinct non-Latin vs Latin scripts
        scripts = set()
        if re.search(r"[\u0B80-\u0BFF]", cleaned):
            scripts.add("ta")
        if re.search(r"[\u0900-\u097F]", cleaned):
            scripts.add("hi")
        if re.search(r"[\u3040-\u30FF\u4E00-\u9FFF]", cleaned):
            scripts.add("ja")
        if re.search(r"[\u0600-\u06FF]", cleaned):
            scripts.add("ar")
        if re.search(r"[\u0C00-\u0C7F]", cleaned):
            scripts.add("te")
        if re.search(r"[\u0D00-\u0D7F]", cleaned):
            scripts.add("ml")
        if re.search(r"[\u0C80-\u0CFF]", cleaned):
            scripts.add("kn")
        if re.search(r"[a-zA-Z]", cleaned):
            scripts.add("latin")

        if len(scripts) >= 2:
            return True

        # Fast exit for monolingual English / plain ASCII Latin text
        if scripts == {"latin"} and not re.search(r"[¿¡ñäöüßéèêëàâôûîïç]", cleaned):
            return False

        # 2. Check sentences in Latin text (sample at most 3 sentences for speed)
        sentences = [
            s.strip()
            for s in re.split(r"[.!?。！？\n]+", cleaned)
            if len(s.strip().split()) >= 2
        ]
        if len(sentences) >= 2:
            detected_langs = set()
            sample_sentences = sentences[:3]
            for s in sample_sentences:
                lang = cls.detect_segment_language(s)
                if lang and lang != "auto":
                    detected_langs.add(lang)
            if len(detected_langs) >= 2:
                return True

        # 3. Check for comma-separated list of known multilingual words
        tokens = [t.strip().lower() for t in re.split(r"[,;、]+", cleaned) if t.strip()]
        if len(tokens) >= 2:
            token_langs = set()
            for t in tokens:
                norm = re.sub(r"^[¡¿!?,.]+|[¡¿!?,.]+$", "", t)
                if norm in KNOWN_EXPRESSIONS:
                    token_langs.add(KNOWN_EXPRESSIONS[norm])
            if len(token_langs) >= 2:
                return True

        return False

    @classmethod
    def detect_segment_language(cls, segment: str) -> str:
        """Detect language of a sentence, clause, or token."""
        cleaned = segment.strip().lower()
        if not cleaned:
            return "auto"

        # Check known expressions
        norm = re.sub(r"^[¡¿!?,.]+|[¡¿!?,.]+$", "", cleaned)
        if norm in KNOWN_EXPRESSIONS:
            return KNOWN_EXPRESSIONS[norm]

        # Script-based detection
        if re.search(r"[\u0B80-\u0BFF]", segment):
            return "ta"
        if re.search(r"[\u0900-\u097F]", segment):
            return "hi"
        if re.search(r"[\u3040-\u30FF\u4E00-\u9FFF]", segment):
            return "ja"
        if re.search(r"[\u0600-\u06FF]", segment):
            return "ar"
        if re.search(r"[\u0C00-\u0C7F]", segment):
            return "te"
        if re.search(r"[\u0D00-\u0D7F]", segment):
            return "ml"
        if re.search(r"[\u0C80-\u0CFF]", segment):
            return "kn"
        if re.search(r"[\uAC00-\uD7AF]", segment):
            return "ko"

        # Latin markers for high accuracy
        if any(c in cleaned for c in ["¿", "¡", "ñ", "estás", "cómo", "está", "qué", "hoy", "buenos"]):
            return "es"
        if any(c in cleaned for c in ["ä", "ö", "ü", "ß", "wunderschöner", "heute", "ist", "ein", "tag"]):
            return "de"
        if any(c in cleaned for c in ["j'", "c'", "d'", "l'", "qu'", "nouvelles", "choses", "apprendre"]):
            return "fr"

        # General detector
        try:
            det = LanguageDetector.detect(segment)
            if det and det.language and det.language != "auto":
                return det.language
        except Exception:
            pass

        return "auto"

    @classmethod
    async def translate_multilingual(
        cls,
        text: str,
        target_language: str,
        translate_fn: Callable[..., Awaitable[str]],
        style: str = "general",
        **extra_kwargs: Any,
    ) -> str:
        """Translates mixed-language input into 100% target language, preserving structure."""
        cleaned = text.strip()
        if not cleaned:
            return ""

        # If text is long (>2500 chars), process via smart chunking with controlled parallelism
        if len(cleaned) > 2500:
            chunks = cls.smart_chunk_text(cleaned, max_chunk_size=2500)
            if len(chunks) > 1:
                sem = asyncio.Semaphore(5)

                async def _trans_subchunk(ch: str) -> str:
                    async with sem:
                        return await cls.translate_multilingual(
                            ch, target_language, translate_fn, style="general", **extra_kwargs
                        )

                chunk_results = await asyncio.gather(*[_trans_subchunk(c) for c in chunks])
                merged = "".join(chunk_results)
                if style != "general":
                    merged = LinguisticAdapter.apply_style(merged, target_language, style)
                return merged

        # Import word cache for word-level memoization
        from app.services.cache import word_cache

        # Split into sentences preserving delimiters
        sentences = re.split(r"([.!?。！？\n]+(?:\s+|$))", cleaned)

        async def _translate_sentence(s: str) -> str:
            if not s.strip():
                return s

            # Check if sentence has comma/clause separation across multiple scripts or languages
            items = re.split(r"(,\s*|\s*;\s*)", s)
            if len(items) > 1:
                item_langs = set()
                for it in items[::2]:
                    if it.strip():
                        item_langs.add(cls.detect_segment_language(it))
                if len(item_langs) >= 2:
                    # Multi-language clause list (e.g. "நன்றி, धन्यवाद, gracias, danke, ありがとう, merci")
                    async def _translate_clause(clause: str) -> str:
                        if not clause.strip():
                            return clause
                        c_lang = cls.detect_segment_language(clause)
                        if c_lang == target_language:
                            return clause
                        ckey = f"{c_lang}:{target_language}:{style}:{clause}"
                        cached_cl = word_cache.get(ckey)
                        if cached_cl is not None:
                            return cached_cl
                        res = await translate_fn(
                            clause, c_lang, target_language, style=style, **extra_kwargs
                        )
                        word_cache.set(ckey, res)
                        return res

                    clause_results = await asyncio.gather(
                        *[_translate_clause(items[j]) for j in range(0, len(items), 2)]
                    )
                    reconstructed = []
                    for k, t_clause in enumerate(clause_results):
                        c_delim = items[k * 2 + 1] if k * 2 + 1 < len(items) else ""
                        reconstructed.append(t_clause + c_delim)
                    return "".join(reconstructed)

            # Single sentence translation
            s_lang = cls.detect_segment_language(s)
            if s_lang == target_language:
                s_trans = s
            else:
                s_trans = await translate_fn(
                    s, s_lang, target_language, style=style, **extra_kwargs
                )

            # Embedded or leftover Latin words when target is non-Latin
            if target_language != "en":
                candidate_words = set(re.findall(r"\b[a-zA-Z]{2,}\b", s_trans))
                valid_words = [
                    w for w in candidate_words
                    if not URL_PATTERN.match(w) and not NUMBER_PATTERN.match(w)
                ]
                if valid_words:
                    async def _translate_single_word(w: str) -> tuple[str, str]:
                        wkey = f"auto:{target_language}:{style}:{w}"
                        cw = word_cache.get(wkey)
                        if cw is not None:
                            return w, cw
                        tw = await translate_fn(
                            w, "auto", target_language, style=style, **extra_kwargs
                        )
                        word_cache.set(wkey, tw)
                        return w, tw

                    word_results = await asyncio.gather(
                        *[_translate_single_word(w) for w in valid_words]
                    )
                    for ew, tw in word_results:
                        if tw.lower() != ew.lower():
                            s_trans = re.sub(r"\b" + re.escape(ew) + r"\b", tw, s_trans)

            return s_trans

        # Translate all independent sentences concurrently
        sentence_texts = [sentences[i] for i in range(0, len(sentences), 2)]
        sentence_results = await asyncio.gather(*[_translate_sentence(s) for s in sentence_texts])

        # Reconstruct in exact original order with original delimiters
        result_chunks: list[str] = []
        for idx, s_res in enumerate(sentence_results):
            delim = sentences[idx * 2 + 1] if idx * 2 + 1 < len(sentences) else ""
            result_chunks.append(s_res + delim)

        final_text = "".join(result_chunks)

        # Normalize Japanese/Chinese fullwidth punctuation if target is Latin or Indian script
        if target_language not in ("ja", "zh"):
            final_text = (
                final_text.replace("。", ". ")
                .replace("！", "! ")
                .replace("？", "? ")
                .replace("、", ", ")
            )
            final_text = re.sub(r"[ ]{2,}", " ", final_text).strip()

        # Apply style if requested
        if style != "general":
            final_text = LinguisticAdapter.apply_style(final_text, target_language, style)

        return final_text
