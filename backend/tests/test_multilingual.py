import pytest
from app.services.multilingual_engine import MultilingualEngine

@pytest.fixture
def anyio_backend():
    return "asyncio"

def test_multilingual_detection():
    # Mixed English, Tamil, Hindi, Spanish, German, Japanese, French
    text = (
        "Hello everyone! இன்று நான் ஒரு புதிய project வேலை செய்து கொண்டிருக்கிறேன். "
        "मेरा लक्ष्य है कि यह translator अलग-अलग भाषाओं को आसानी से समझ सके. ¿Cómo estás hoy? "
        "Heute ist ein wunderschöner Tag. 私は新しいことを学ぶのが好きです。 "
        "J'aime apprendre de nouvelles choses. Technology can connect people from different countries. "
        "நன்றி, धन्यवाद, gracias, danke, ありがとう, merci!"
    )
    assert MultilingualEngine.is_multilingual(text) is True

    # Simple monolingual texts
    assert MultilingualEngine.is_multilingual("Hello world, how are you?") is False
    assert MultilingualEngine.is_multilingual("வணக்கம், நீங்கள் நலமாக இருக்கிறீர்களா?") is False
    assert MultilingualEngine.is_multilingual("नमस्ते, आप कैसे हैं?") is False

@pytest.mark.anyio
async def test_multilingual_translation_into_tamil():
    text = (
        "Hello everyone! இன்று நான் ஒரு புதிய project வேலை செய்து கொண்டிருக்கிறேன். "
        "मेरा लक्ष्य है कि यह translator अलग-अलग भाषाओं को आसानी से समझ सके. ¿Cómo estás hoy? "
        "Heute ist ein wunderschöner Tag. 私は新しいことを学ぶのが好きです。 "
        "J'aime apprendre de nouvelles choses. Technology can connect people from different countries. "
        "நன்றி, धन्यवाद, gracias, danke, ありがとう, merci!"
    )

    async def mock_translate(seg_text, seg_src, seg_tgt, **kwargs):
        # Return Tamil translation
        return "வணக்கம்"

    result = await MultilingualEngine.translate_multilingual(
        text, "ta", mock_translate
    )
    assert len(result) > 0
    # Confirm it produced translated text
    assert "வணக்கம்" in result
