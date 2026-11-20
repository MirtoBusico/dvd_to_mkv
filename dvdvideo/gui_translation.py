"""Translation catalog selection for the GTK interface."""

from __future__ import annotations

import gettext
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locale"


def identity(message: str) -> str:
    return message


def load_translation(language: str) -> gettext.NullTranslations:
    if language == "en":
        return gettext.NullTranslations()
    languages = None if language == "system" else [language]
    return gettext.translation(
        "dvd-to-mkv", localedir=LOCALE_DIR, languages=languages,
        fallback=language == "system",
    )
