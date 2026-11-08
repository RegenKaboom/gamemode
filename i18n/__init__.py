"""
Game Mode - Internationalization (i18n) Module
Supports English (default), Portuguese (Brazil), and Spanish
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Default language is English
DEFAULT_LANG = "en"
SUPPORTED_LANGS = ["en", "pt", "es"]

# Language display names
LANG_NAMES = {
    "en": "English",
    "pt": "Português (Brasil)",
    "es": "Español"
}

# Theme options
THEMES = {
    "light": {"en": "Light", "pt": "Claro", "es": "Claro"},
    "dark": {"en": "Dark", "pt": "Escuro", "es": "Oscuro"},
    "system": {"en": "System Default", "pt": "Padrão do Sistema", "es": "Predeterminado del Sistema"}
}

class I18n:
    def __init__(self, lang: str = DEFAULT_LANG):
        self.lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
        self._translations: Dict[str, Any] = {}
        self._load_translations()

    def _load_translations(self):
        """Load translations for current language"""
        base_path = Path(__file__).parent
        lang_file = base_path / f"{self.lang}.json"

        if lang_file.exists():
            with open(lang_file, 'r', encoding='utf-8') as f:
                self._translations = json.load(f)
        else:
            # Fallback to English
            fallback_file = base_path / f"{DEFAULT_LANG}.json"
            if fallback_file.exists():
                with open(fallback_file, 'r', encoding='utf-8') as f:
                    self._translations = json.load(f)
            else:
                self._translations = {}

    def set_language(self, lang: str):
        """Change language and reload translations"""
        if lang in SUPPORTED_LANGS:
            self.lang = lang
            self._load_translations()

    def t(self, key: str, **kwargs) -> str:
        """Translate a key with optional formatting

        Args:
            key: Dot-separated path to translation (e.g., "game_tab.priority_label")
            **kwargs: Format arguments for the translation string

        Returns:
            Translated string or key if not found
        """
        keys = key.split('.')
        value = self._translations

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Fallback to English if key not found
                return self._fallback_translate(key, **kwargs)

        if isinstance(value, str):
            try:
                return value.format(**kwargs) if kwargs else value
            except KeyError:
                return value
        return key

    def _fallback_translate(self, key: str, **kwargs) -> str:
        """Try to get translation from English fallback"""
        if self.lang != DEFAULT_LANG:
            base_path = Path(__file__).parent
            en_file = base_path / f"{DEFAULT_LANG}.json"
            if en_file.exists():
                with open(en_file, 'r', encoding='utf-8') as f:
                    en_translations = json.load(f)

                keys = key.split('.')
                value = en_translations
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return key
                if isinstance(value, str):
                    try:
                        return value.format(**kwargs) if kwargs else value
                    except KeyError:
                        return value
        return key

    def get_theme_name(self, theme: str) -> str:
        """Get localized theme name"""
        if theme in THEMES:
            return THEMES[theme].get(self.lang, THEMES[theme][DEFAULT_LANG])
        return theme

    def get_lang_name(self, lang: str) -> str:
        """Get localized language name"""
        return LANG_NAMES.get(lang, lang)

    @property
    def current_lang(self) -> str:
        return self.lang

    @property
    def is_rtl(self) -> bool:
        """Check if current language is RTL (none of our langs are)"""
        return False


# Global instance
_i18n: Optional[I18n] = None

def get_i18n() -> I18n:
    """Get global i18n instance"""
    global _i18n
    if _i18n is None:
        _i18n = I18n()
    return _i18n

def set_language(lang: str):
    """Set global language"""
    global _i18n
    if _i18n is None:
        _i18n = I18n(lang)
    else:
        _i18n.set_language(lang)

def t(key: str, **kwargs) -> str:
    """Global translate function"""
    return get_i18n().t(key, **kwargs)