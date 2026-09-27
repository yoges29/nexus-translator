import logging
import re
from typing import ClassVar

from app.core.errors import AppError, ProviderError
from app.services.detector import LanguageDetector
from app.services.linguistic_adapter import LinguisticAdapter
from app.services.providers.base import (
    DetectionResult,
    OfflineTranslationProvider,
)

logger = logging.getLogger("nexus.translator.provider.offline")


class OfflineLocalTranslationProvider(OfflineTranslationProvider):
    """Local offline translation provider.

    Does NOT make external network requests. Uses an offline lexical phrasebook
    and rule-based linguistic transformation engine.
    Supported offline language pairs:
    - en <-> ta (English - Tamil)
    - en <-> es (English - Spanish)
    - en <-> fr (English - French)
    - en <-> de (English - German)
    - en <-> hi (English - Hindi)
    """

    SUPPORTED_PAIRS: ClassVar[set[tuple[str, str]]] = {
        ("en", "ta"),
        ("ta", "en"),
        ("en", "es"),
        ("es", "en"),
        ("en", "fr"),
        ("fr", "en"),
        ("en", "de"),
        ("de", "en"),
        ("en", "hi"),
        ("hi", "en"),
    }

    # High-frequency dictionary & phrases
    PHRASEBOOK: ClassVar[dict[tuple[str, str], dict[str, str]]] = {
        ("en", "ta"): {
            "hello": "வணக்கம்",
            "hi": "வணக்கம்",
            "welcome": "நல்வரவு",
            "how are you": "நீங்கள் எப்படி இருக்கிறீர்கள்",
            "how are you?": "நீங்கள் எப்படி இருக்கிறீர்கள்?",
            "good morning": "காலை வணக்கம்",
            "good afternoon": "மதிய வணக்கம்",
            "good evening": "மாலை வணக்கம்",
            "good night": "இரவு வணக்கம்",
            "thank you": "நன்றி",
            "thanks": "நன்றி",
            "yes": "ஆம்",
            "no": "இல்லை",
            "please": "தயவுசெய்து",
            "goodbye": "போய் வருகிறேன்",
            "bye": "போய் வருகிறேன்",
            "see you later": "பிறகு சந்திப்போம்",
            "what is your name": "உங்கள் பெயர் என்ன",
            "what is your name?": "உங்கள் பெயர் என்ன?",
            "my name is": "என் பெயர்",
            "where are you from": "நீங்கள் எங்கிருந்து வருகிறீர்கள்",
            "i understand": "எனக்கு புரிகிறது",
            "i do not understand": "எனக்கு புரியவில்லை",
            "help": "உதவி",
            "water": "தண்ணீர்",
            "food": "உணவு",
            "friend": "நண்பர்",
            "today": "இன்று",
            "tomorrow": "நாளை",
            "yesterday": "நேற்று",
            "good": "நல்லது",
            "bad": "மோசமானது",
            "nexus translator": "நெக்ஸஸ் மொழிபெயர்ப்பாளர்",
        },
        ("ta", "en"): {
            "வணக்கம்": "Hello",
            "நல்வரவு": "Welcome",
            "நீங்கள் எப்படி இருக்கிறீர்கள்": "How are you",
            "நீங்கள் எப்படி இருக்கிறீர்கள்?": "How are you?",
            "காலை வணக்கம்": "Good morning",
            "மாலை வணக்கம்": "Good evening",
            "இரவு வணக்கம்": "Good night",
            "நன்றி": "Thank you",
            "ஆம்": "Yes",
            "இல்லை": "No",
            "தயவுசெய்து": "Please",
            "போய் வருகிறேன்": "Goodbye",
            "உங்கள் பெயர் என்ன": "What is your name",
            "உங்கள் பெயர் என்ன?": "What is your name?",
            "என் பெயர்": "My name is",
            "உதவி": "Help",
            "தண்ணீர்": "Water",
            "உணவு": "Food",
            "நண்பர்": "Friend",
            "இன்று": "Today",
            "நாளை": "Tomorrow",
            "நெக்ஸஸ் மொழிபெயர்ப்பாளர்": "Nexus Translator",
        },
        ("en", "es"): {
            "hello": "hola",
            "hi": "hola",
            "welcome": "bienvenido",
            "how are you": "cómo estás",
            "how are you?": "¿cómo estás?",
            "good morning": "buenos días",
            "good afternoon": "buenas tardes",
            "good night": "buenas noches",
            "thank you": "gracias",
            "thanks": "gracias",
            "yes": "sí",
            "no": "no",
            "please": "por favor",
            "goodbye": "adiós",
            "bye": "adiós",
            "see you later": "hasta luego",
            "what is your name": "cómo te llamas",
            "what is your name?": "¿cómo te llamas?",
            "my name is": "mi nombre es",
            "help": "ayuda",
            "water": "agua",
            "friend": "amigo",
            "today": "hoy",
            "good": "bueno",
        },
        ("es", "en"): {
            "hola": "Hello",
            "bienvenido": "Welcome",
            "cómo estás": "How are you",
            "buenos días": "Good morning",
            "buenas tardes": "Good afternoon",
            "buenas noches": "Good night",
            "gracias": "Thank you",
            "sí": "Yes",
            "no": "No",
            "por favor": "Please",
            "adiós": "Goodbye",
            "hasta luego": "See you later",
            "ayuda": "Help",
            "agua": "Water",
            "amigo": "Friend",
        },
        ("en", "fr"): {
            "hello": "bonjour",
            "hi": "salut",
            "welcome": "bienvenue",
            "how are you": "comment allez-vous",
            "how are you?": "comment allez-vous ?",
            "good morning": "bonjour",
            "good evening": "bonsoir",
            "good night": "bonne nuit",
            "thank you": "merci",
            "thanks": "merci",
            "yes": "oui",
            "no": "non",
            "please": "s'il vous plaît",
            "goodbye": "au revoir",
            "bye": "salut",
            "see you later": "à plus tard",
            "help": "aide",
            "water": "eau",
            "friend": "ami",
        },
        ("fr", "en"): {
            "bonjour": "Hello",
            "salut": "Hi",
            "bienvenue": "Welcome",
            "comment allez-vous": "How are you",
            "bonsoir": "Good evening",
            "bonne nuit": "Good night",
            "merci": "Thank you",
            "oui": "Yes",
            "non": "No",
            "au revoir": "Goodbye",
            "aide": "Help",
            "eau": "Water",
            "ami": "Friend",
        },
        ("en", "de"): {
            "hello": "hallo",
            "hi": "hallo",
            "welcome": "willkommen",
            "how are you": "wie geht es dir",
            "how are you?": "wie geht es dir?",
            "good morning": "guten morgen",
            "good evening": "guten abend",
            "good night": "gute nacht",
            "thank you": "danke",
            "thanks": "danke",
            "yes": "ja",
            "no": "nein",
            "please": "bitte",
            "goodbye": "auf wiedersehen",
            "help": "hilfe",
            "water": "wasser",
            "friend": "freund",
        },
        ("de", "en"): {
            "hallo": "Hello",
            "willkommen": "Welcome",
            "wie geht es dir": "How are you",
            "guten morgen": "Good morning",
            "guten abend": "Good evening",
            "gute nacht": "Good night",
            "danke": "Thank you",
            "ja": "Yes",
            "nein": "No",
            "bitte": "Please",
            "auf wiedersehen": "Goodbye",
            "hilfe": "Help",
            "wasser": "Water",
            "freund": "Friend",
        },
        ("en", "hi"): {
            "hello": "नमस्ते",
            "hi": "नमस्ते",
            "welcome": "स्वागत हे",
            "how are you": "आप कैसे हैं",
            "how are you?": "आप कैसे हैं?",
            "good morning": "शुभ प्रभात",
            "good evening": "शुभ संध्या",
            "good night": "शुभ रात्रि",
            "thank you": "धन्यवाद",
            "thanks": "धन्यवाद",
            "yes": "हाँ",
            "no": "नहीं",
            "please": "कृपया",
            "goodbye": "अलविदा",
            "help": "मदद",
            "water": "पानी",
            "friend": "दोस्त",
        },
        ("hi", "en"): {
            "नमस्ते": "Hello",
            "स्वागत हे": "Welcome",
            "आप कैसे हैं": "How are you",
            "शुभ प्रभात": "Good morning",
            "शुभ संध्या": "Good evening",
            "शुभ रात्रि": "Good night",
            "धन्यवाद": "Thank you",
            "हाँ": "Yes",
            "नहीं": "No",
            "कृपया": "Please",
            "अलविदा": "Goodbye",
            "मदद": "Help",
            "पानी": "Water",
            "दोस्त": "Friend",
        },
    }

    def is_pair_supported(self, source_language: str, target_language: str) -> bool:
        src = source_language.strip().lower()
        tgt = target_language.strip().lower()
        return (src, tgt) in self.SUPPORTED_PAIRS

    def get_supported_pairs(self) -> list[dict[str, str]]:
        return [{"source": s, "target": t} for s, t in sorted(self.SUPPORTED_PAIRS)]

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> str:
        src = source_language.strip().lower()
        tgt = target_language.strip().lower()

        if not self.is_pair_supported(src, tgt):
            supported_str = ", ".join(f"{s}➔{t}" for s, t in sorted(self.SUPPORTED_PAIRS))
            raise AppError(
                f"Offline translation is not supported for language pair '{src}' ➔ '{tgt}'. "
                f"Supported offline pairs are: [{supported_str}]. Please connect to the internet or switch to Online mode.",
                status_code=400,
            )

        cleaned = text.strip()
        if not cleaned:
            return ""

        table = self.PHRASEBOOK.get((src, tgt), {})

        # 1. Exact phrase match
        normalized = cleaned.lower().strip()
        if normalized in table:
            result = table[normalized]
            if style != "general":
                return LinguisticAdapter.apply_style(result, tgt, style)
            return result

        # 2. Match without punctuation
        punct_stripped = re.sub(r"[?!.,;:]+$", "", normalized).strip()
        punct_end = cleaned[len(punct_stripped) :] if len(cleaned) > len(punct_stripped) else ""
        if punct_stripped in table:
            result = table[punct_stripped] + punct_end
            if style != "general":
                return LinguisticAdapter.apply_style(result, tgt, style)
            return result

        # 3. Token-by-token offline lexical mapping
        words = re.findall(r"[\w]+|[^\w\s]", cleaned, re.UNICODE)
        translated_tokens: list[str] = []
        for word in words:
            word_lower = word.lower()
            if word_lower in table:
                mapped = table[word_lower]
                # Match capitalization if target is latin
                if word.istitle() and tgt in ("en", "es", "fr", "de"):
                    mapped = mapped.capitalize()
                translated_tokens.append(mapped)
            else:
                translated_tokens.append(word)

        result = ""
        for i, token in enumerate(translated_tokens):
            if i > 0 and not re.match(r"^[^\w\s]$", token):
                result += " "
            result += token

        if style != "general":
            return LinguisticAdapter.apply_style(result, tgt, style)
        return result

    async def detect_language(self, text: str) -> DetectionResult:
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
