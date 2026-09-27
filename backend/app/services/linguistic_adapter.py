import re
from typing import Literal

TranslationStyle = Literal["general", "formal", "casual"]

# Stylistic and grammatical transformation mappings for formal / casual modes
# Supports major languages: Tamil, Hindi, Telugu, Malayalam, Kannada, Japanese, Korean, French, German, Spanish, Chinese, Arabic, English

STYLE_TRANSFORMS: dict[str, dict[str, list[tuple[re.Pattern[str], str]]]] = {
    # German: Formal (Siezen) vs Casual (Duzen)
    "de": {
        "formal": [
            (re.compile(r"\bdu\b", re.IGNORECASE), "Sie"),
            (re.compile(r"\bdir\b", re.IGNORECASE), "Ihnen"),
            (re.compile(r"\bdich\b", re.IGNORECASE), "Sie"),
            (re.compile(r"\bdein\b", re.IGNORECASE), "Ihr"),
            (re.compile(r"\bdeine\b", re.IGNORECASE), "Ihre"),
            (re.compile(r"\bdeinem\b", re.IGNORECASE), "Ihrem"),
            (re.compile(r"\bdeinen\b", re.IGNORECASE), "Ihren"),
            (re.compile(r"\bbist\b", re.IGNORECASE), "sind"),
            (re.compile(r"\bhast\b", re.IGNORECASE), "haben"),
            (re.compile(r"\bkannst\b", re.IGNORECASE), "können"),
        ],
        "casual": [
            (re.compile(r"\bSie\b"), "du"),
            (re.compile(r"\bIhnen\b"), "dir"),
            (re.compile(r"\bIhr\b"), "dein"),
            (re.compile(r"\bIhre\b"), "deine"),
            (re.compile(r"\bIhrem\b"), "deinem"),
            (re.compile(r"\bIhren\b"), "deinen"),
            (re.compile(r"\bsind\b", re.IGNORECASE), "bist"),
            (re.compile(r"\bhaben\b", re.IGNORECASE), "hast"),
            (re.compile(r"\bkönnen\b", re.IGNORECASE), "kannst"),
        ],
    },
    # French: Formal (Vouvoiement) vs Casual (Tutoiement)
    "fr": {
        "formal": [
            (re.compile(r"\btu\b", re.IGNORECASE), "vous"),
            (re.compile(r"\bte\b", re.IGNORECASE), "vous"),
            (re.compile(r"\btoi\b", re.IGNORECASE), "vous"),
            (re.compile(r"\bton\b", re.IGNORECASE), "votre"),
            (re.compile(r"\bta\b", re.IGNORECASE), "votre"),
            (re.compile(r"\btes\b", re.IGNORECASE), "vos"),
            (re.compile(r"\bes\b", re.IGNORECASE), "êtes"),
            (re.compile(r"\bas\b", re.IGNORECASE), "avez"),
            (re.compile(r"\bpeux\b", re.IGNORECASE), "pouvez"),
            (re.compile(r"\bs'il te plaît\b", re.IGNORECASE), "s'il vous plaît"),
        ],
        "casual": [
            (re.compile(r"\bvous\b", re.IGNORECASE), "tu"),
            (re.compile(r"\bvotre\b", re.IGNORECASE), "ton"),
            (re.compile(r"\bvos\b", re.IGNORECASE), "tes"),
            (re.compile(r"\bêtes\b", re.IGNORECASE), "es"),
            (re.compile(r"\bavez\b", re.IGNORECASE), "as"),
            (re.compile(r"\bpouvez\b", re.IGNORECASE), "peux"),
            (re.compile(r"\bs'il vous plaît\b", re.IGNORECASE), "s'il te plaît"),
            (re.compile(r"\bbonjour\b", re.IGNORECASE), "salut"),
        ],
    },
    # Spanish: Formal (Usted) vs Casual (Tú)
    "es": {
        "formal": [
            (re.compile(r"\btú\b", re.IGNORECASE), "usted"),
            (re.compile(r"\btu\b", re.IGNORECASE), "su"),
            (re.compile(r"\btus\b", re.IGNORECASE), "sus"),
            (re.compile(r"\bti\b", re.IGNORECASE), "usted"),
            (re.compile(r"\bte\b", re.IGNORECASE), "le"),
            (re.compile(r"\beres\b", re.IGNORECASE), "es"),
            (re.compile(r"\btienes\b", re.IGNORECASE), "tiene"),
            (re.compile(r"\bpuedes\b", re.IGNORECASE), "puede"),
            (re.compile(r"\bquieres\b", re.IGNORECASE), "quiere"),
            (re.compile(r"\bpor favor\b", re.IGNORECASE), "por favor, tenga la amabilidad"),
        ],
        "casual": [
            (re.compile(r"\busted\b", re.IGNORECASE), "tú"),
            (re.compile(r"\bsu\b", re.IGNORECASE), "tu"),
            (re.compile(r"\bsus\b", re.IGNORECASE), "tus"),
            (re.compile(r"\bes\b", re.IGNORECASE), "eres"),
            (re.compile(r"\btiene\b", re.IGNORECASE), "tienes"),
            (re.compile(r"\bpuede\b", re.IGNORECASE), "puedes"),
            (re.compile(r"\bhola\b", re.IGNORECASE), "¡hola qué tal!"),
        ],
    },
    # Hindi: Formal (आप) vs Casual (तुम / तू)
    "hi": {
        "formal": [
            (re.compile(r"\bतुम\b"), "आप"),
            (re.compile(r"\bतू\b"), "आप"),
            (re.compile(r"\bतुम्हारा\b"), "आपका"),
            (re.compile(r"\bतुम्हारी\b"), "आपकी"),
            (re.compile(r"\bतुम्हारे\b"), "आपके"),
            (re.compile(r"\bतुझे\b"), "आपको"),
            (re.compile(r"\bतुम्हें\b"), "आपको"),
            (re.compile(r"\bहो\b"), "हैं"),
            (re.compile(r"\bकरो\b"), "कीजिए"),
            (re.compile(r"\bबताओ\b"), "बताइए"),
            (re.compile(r"\bआओ\b"), "आइए"),
            (re.compile(r"\bजाओ\b"), "जाइए"),
        ],
        "casual": [
            (re.compile(r"\bआप\b"), "तुम"),
            (re.compile(r"\bआपका\b"), "तुम्हारा"),
            (re.compile(r"\bआपकी\b"), "तुम्हारी"),
            (re.compile(r"\bआपके\b"), "तुम्हारे"),
            (re.compile(r"\bआपको\b"), "तुम्हें"),
            (re.compile(r"\bकीजिए\b"), "करो"),
            (re.compile(r"\bबताइए\b"), "बताओ"),
            (re.compile(r"\bआइए\b"), "आओ"),
            (re.compile(r"\bनमस्ते\b"), "हैलो"),
        ],
    },
    # Tamil: Formal (நீங்கள் / மரியாதை) vs Casual (நீ / பேச்சு வழக்கு)
    "ta": {
        "formal": [
            (re.compile(r"\bநீ\b"), "நீங்கள்"),
            (re.compile(r"\bஉன்\b"), "உங்கள்"),
            (re.compile(r"\bஉனக்கு\b"), "உங்களுக்கு"),
            (re.compile(r"\bஉன்னை\b"), "உங்களை"),
            (re.compile(r"இருக்கிறாய்"), "இருக்கிறீர்கள்"),
            (re.compile(r"இருக்கீங்க"), "இருக்கிறீர்கள்"),
            (re.compile(r"செய்\b"), "செய்யுங்கள்"),
            (re.compile(r"வா\b"), "வாருங்கள்"),
            (re.compile(r"போ\b"), "போங்கள்"),
            (re.compile(r"சொல்\b"), "சொல்லுங்கள்"),
        ],
        "casual": [
            (re.compile(r"\bநீங்கள்\b"), "நீ"),
            (re.compile(r"\bஉங்கள்\b"), "உன்"),
            (re.compile(r"\bஉங்களுக்கு\b"), "உனக்கு"),
            (re.compile(r"\bஉங்களை\b"), "உன்னை"),
            (re.compile(r"இருக்கிறீர்கள்"), "இருக்கீங்க"),
            (re.compile(r"செய்யுங்கள்"), "செய்"),
            (re.compile(r"வாருங்கள்"), "வா"),
            (re.compile(r"வணக்கம்"), "ஹாய்"),
        ],
    },
    # Japanese: Formal (丁寧語・敬語 / です・ます) vs Casual (普通体 / だ・である)
    "ja": {
        "formal": [
            (re.compile(r"だ$|だ。"), "です。"),
            (re.compile(r"である$|である。"), "でございます。"),
            (re.compile(r"する$|する。"), "します。"),
            (re.compile(r"ない$|ない。"), "ありません。"),
            (re.compile(r"行った$|行った。"), "行きました。"),
            (re.compile(r"食べた$|食べた。"), "食べました。"),
            (re.compile(r"ありがとう$"), "ありがとうございます。"),
            (re.compile(r"こんにちは$"), "こんにちは、よろしくお願いします。"),
        ],
        "casual": [
            (re.compile(r"です$|です。"), "だよ。"),
            (re.compile(r"でございます$|でございます。"), "だよ。"),
            (re.compile(r"します$|します。"), "するよ。"),
            (re.compile(r"ありません$|ありません。"), "ないよ。"),
            (re.compile(r"行きました$|行きました。"), "行ったよ。"),
            (re.compile(r"ありがとうございます"), "ありがとう"),
        ],
    },
    # Korean: Formal (존댓말 / 습니다・해요) vs Casual (반말 / 해・야)
    "ko": {
        "formal": [
            (re.compile(r"해$|해\."), "합니다."),
            (re.compile(r"야$|야\."), "입니다."),
            (re.compile(r"고마워$|고마워\."), "감사합니다."),
            (re.compile(r"안녕$|안녕\."), "안녕하세요."),
            (re.compile(r"있어$|있어\."), "있습니다."),
        ],
        "casual": [
            (re.compile(r"합니다$|합니다\."), "해."),
            (re.compile(r"입니다$|입니다\."), "이야."),
            (re.compile(r"감사합니다$|감사합니다\."), "고마워."),
            (re.compile(r"안녕하세요$|안녕하세요\."), "안녕."),
            (re.compile(r"있습니다$|있습니다\."), "있어."),
        ],
    },
}


class LinguisticAdapter:
    """Provides style adaptation (General/Formal/Casual) and intelligent translation alternatives."""

    @classmethod
    def apply_style(cls, text: str, target_language: str, style: str = "general") -> str:
        lang = target_language.strip().lower()
        style_key = style.strip().lower()

        if style_key not in ("formal", "casual"):
            return text

        lang_rules = STYLE_TRANSFORMS.get(lang, {}).get(style_key)
        if not lang_rules:
            # Language does not have distinct formal/casual rules configured -> gracefully return text
            return text

        transformed = text
        for pattern, replacement in lang_rules:
            transformed = pattern.sub(replacement, transformed)

        return transformed

    @classmethod
    def generate_alternatives(
        cls,
        primary_translation: str,
        source_language: str,
        target_language: str,
        style: str = "general",
    ) -> list[str]:
        """Generates up to 3 distinct linguistic alternatives preserving the meaning of the primary translation."""
        lang = target_language.strip().lower()
        cleaned_primary = primary_translation.strip()
        if not cleaned_primary:
            return []

        alternatives: list[str] = []

        # 1. Generate register-shifted variation (Formal vs Casual vs General)
        if style == "general":
            formal_var = cls.apply_style(cleaned_primary, lang, "formal")
            casual_var = cls.apply_style(cleaned_primary, lang, "casual")
            if formal_var and formal_var != cleaned_primary and formal_var not in alternatives:
                alternatives.append(formal_var)
            if casual_var and casual_var != cleaned_primary and casual_var not in alternatives:
                alternatives.append(casual_var)
        elif style == "formal":
            gen_var = cls.apply_style(cleaned_primary, lang, "casual")
            if gen_var and gen_var != cleaned_primary and gen_var not in alternatives:
                alternatives.append(gen_var)
        elif style == "casual":
            gen_var = cls.apply_style(cleaned_primary, lang, "formal")
            if gen_var and gen_var != cleaned_primary and gen_var not in alternatives:
                alternatives.append(gen_var)

        # 2. Language-specific natural paraphrasing and synonym alternations
        if lang == "ta":
            # Tamil natural conversational phrasing
            if "எப்படி இருக்கிறீர்கள்" in cleaned_primary or "எப்படி இருக்கீங்க" in cleaned_primary:
                for alt in ["நலமாக இருக்கிறீர்களா?", "எப்படி இருக்கீங்க?", "சௌக்கியமா இருக்கீங்களா?"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "வணக்கம்" in cleaned_primary:
                for alt in ["நல்வரவு!", "வணக்கங்கள்!"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "நன்றி" in cleaned_primary:
                for alt in ["மிக்க நன்றி!", "ரொம்ப நன்றி!"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)

        elif lang == "hi":
            # Hindi natural conversational phrasing
            if "आप कैसे हैं" in cleaned_primary or "कैसे हो" in cleaned_primary:
                for alt in ["क्या हालचाल है?", "सब कुशल मंगल है?", "आप कैसे हो?"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "नमस्ते" in cleaned_primary:
                for alt in ["नमस्कार!", "प्रणाम!"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "धन्यवाद" in cleaned_primary:
                for alt in ["बहुत बहुत धन्यवाद!", "शुक्रिया!"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)

        elif lang == "ja":
            # Japanese natural conversational phrasing
            if "元気ですか" in cleaned_primary or "いかがですか" in cleaned_primary:
                for alt in ["お元気でお過ごしですか？", "調子はどうですか？", "いかがお過ごしですか？"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "ありがとう" in cleaned_primary:
                for alt in ["誠にありがとうございます。", "どうもありがとう！"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)

        elif lang == "fr":
            # French natural conversational phrasing
            if "comment allez-vous" in cleaned_primary.lower() or "comment vas-tu" in cleaned_primary.lower():
                for alt in ["Comment ça va ?", "Comment vas-tu ?", "Vous allez bien ?"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "merci" in cleaned_primary.lower():
                for alt in ["Merci beaucoup !", "Je vous remercie bien."]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)

        elif lang == "es":
            # Spanish natural conversational phrasing
            if "¿cómo estás?" in cleaned_primary.lower() or "¿cómo está?" in cleaned_primary.lower():
                for alt in ["¿Qué tal estás?", "¿Cómo te va?", "¿Todo bien?"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "gracias" in cleaned_primary.lower():
                for alt in ["¡Muchas gracias!", "Mil gracias."]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)

        elif lang == "de":
            # German natural conversational phrasing
            if "wie geht es ihnen" in cleaned_primary.lower() or "wie geht es dir" in cleaned_primary.lower():
                for alt in ["Wie geht's dir?", "Alles gut bei Ihnen?", "Wie läuft es?"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "danke" in cleaned_primary.lower():
                for alt in ["Vielen Dank!", "Herzlichen Dank!"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)

        elif lang == "en":
            # English phrasing alternatives
            if "how are you" in cleaned_primary.lower():
                for alt in ["How is it going?", "How have you been?", "How are things?"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "hello" in cleaned_primary.lower():
                for alt in ["Hi there!", "Greetings!"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)
            elif "thank you" in cleaned_primary.lower():
                for alt in ["Thanks a lot!", "Much appreciated!"]:
                    if alt != cleaned_primary and alt not in alternatives:
                        alternatives.append(alt)

        # 3. If no specific rule matched and we have less than 1 alternative, generate polite particle/phrasing variant if punctuation permits
        if not alternatives:
            # Punctuation/cadence variations
            if cleaned_primary.endswith("."):
                alt = cleaned_primary[:-1] + "!"
                if alt != cleaned_primary:
                    alternatives.append(alt)

        # Ensure unique items, max 3 items
        unique_alts = []
        for alt in alternatives:
            if alt not in unique_alts and alt != cleaned_primary:
                unique_alts.append(alt)
            if len(unique_alts) >= 3:
                break

        return unique_alts
