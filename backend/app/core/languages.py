import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger("nexus.translator")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


@lru_cache
def load_language_registry() -> dict[str, Any]:
    settings = get_settings()
    path: Path = settings.languages_path
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    return data


def get_languages() -> list[dict[str, Any]]:
    return load_language_registry()["languages"]


def get_language_by_code(code: str) -> dict[str, Any] | None:
    normalized = code.strip().lower()
    for language in get_languages():
        if language["code"] == normalized:
            return language
    return None


def is_translation_supported(code: str) -> bool:
    if code == "auto":
        return True
    language = get_language_by_code(code)
    return bool(language and language.get("translationSupported"))
