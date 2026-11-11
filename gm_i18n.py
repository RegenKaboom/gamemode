"""Language and theme choice for Game Mode, plus the tr() translator.

The program's own texts are written in Portuguese in the source; tr() turns them into English
or Spanish through the tables in gm_lang.py. Unknown texts come back unchanged, so a missing
translation never breaks anything.

Order of choice (language and theme): what the user picked in Options > Accessibility,
then what the installer saved (installer_prefs.json), then (for people who already used an
older version) the dark theme they had, then the Windows language/theme.
"""
import json
import os
import sys

LANG_CHOICES = ("auto", "en", "pt", "es")
THEME_CHOICES = ("auto", "dark", "light")
LANG_NAMES = {"en": "English", "pt": "Português", "es": "Español"}

_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "GameModeLite")
SETTINGS_PATH = os.path.join(_DIR, "settings.json")
PREFS_PATH = os.path.join(_DIR, "installer_prefs.json")

_state = {"lang": None, "theme": None}
_tables = None


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def system_lang():
    """'pt', 'es' or 'en' from the Windows display language (English for anything else)."""
    try:
        import ctypes
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFF
        return {0x16: "pt", 0x0A: "es"}.get(primary, "en")
    except Exception:
        pass
    code = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "en")[:2].lower()
    return code if code in ("pt", "es") else "en"


def system_theme():
    """'light' or 'dark' following the Windows app theme (dark if it cannot tell)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
    except Exception:
        return "dark"


def choices(settings_path=None, prefs_path=None):
    """What was chosen, before looking at Windows: (lang, theme), each one of auto/en/pt/es and auto/dark/light."""
    saved = _load_json(settings_path or SETTINGS_PATH)
    prefs = _load_json(prefs_path or PREFS_PATH) or {}
    ui = (saved or {}).get("ui") if isinstance((saved or {}).get("ui"), dict) else {}

    def pick(key, allowed):
        for source in (ui, prefs):          # the user's own choice beats the installer's
            if source.get(key) in allowed:
                return source[key]
        return ""

    lang = pick("lang", LANG_CHOICES) or "auto"
    theme = pick("theme", THEME_CHOICES)
    if not theme:
        # An older install that never chose keeps the dark look it always had; a new one follows Windows.
        theme = "dark" if saved is not None else "auto"
    return lang, theme


def resolve(settings_path=None, prefs_path=None):
    """Works out (lang, theme) as real values: en/pt/es and dark/light."""
    lang, theme = choices(settings_path, prefs_path)
    return (system_lang() if lang == "auto" else lang), (system_theme() if theme == "auto" else theme)


def init(settings_path=None, prefs_path=None):
    _state["lang"], _state["theme"] = resolve(settings_path, prefs_path)
    return _state["lang"], _state["theme"]


def lang():
    if _state["lang"] is None:
        init()
    return _state["lang"]


def theme():
    if _state["theme"] is None:
        init()
    return _state["theme"]


def _get_tables():
    global _tables
    if _tables is None:
        try:
            import gm_lang
            _tables = gm_lang.TABLE
        except Exception:
            _tables = {}
    return _tables


def tr(text):
    """Translate a program text. Portuguese (the source language) and unknown texts pass through."""
    code = lang()
    if code == "pt" or not isinstance(text, str):
        return text
    row = _get_tables().get(text)
    if row is None:
        return text
    return row[0] if code == "en" else row[1]


# ---- palettes ---------------------------------------------------------------------

DARK = {
    "BG": "#14151a", "SIDE": "#191b21", "CARD": "#1b1d24", "PANEL": "#23262e", "BORDER": "#2a2d36",
    "TEXT": "#e8eaf0", "MUTED": "#8b909c", "ACCENT": "#4f8cff", "GREEN": "#35d07f",
    "WARN": "#f5a623", "PINK": "#c678dd", "TEAL": "#2ec4b6",
    "SEL": "#22304f", "ACCENT_HOVER": "#3d78e6", "OFF": "#3a3d47", "OFF_DIS": "#2c2e36",
    "KNOB_DIS": "#6b6f7a", "ICON": "#9aa0ab", "ICON_HOVER": "#c5c9d3", "ICON_BG": "#1f2a44",
    "BTN_BG": "#12131a", "GLOW1": "#172340", "GLOW2": "#1a2a4d", "GLOW3": "#203764",
}
LIGHT = {
    "BG": "#f4f5f8", "SIDE": "#eceef3", "CARD": "#ffffff", "PANEL": "#e4e8ef", "BORDER": "#cdd3de",
    "TEXT": "#1b1e27", "MUTED": "#566074", "ACCENT": "#2559c9", "GREEN": "#0f7a44",
    "WARN": "#a85a00", "PINK": "#963aae", "TEAL": "#0b7a70",
    "SEL": "#cfdcf7", "ACCENT_HOVER": "#1d49a8", "OFF": "#b9c0cd", "OFF_DIS": "#d9dde5",
    "KNOB_DIS": "#f1f3f7", "ICON": "#6a7386", "ICON_HOVER": "#2b3140", "ICON_BG": "#dbe5fb",
    "BTN_BG": "#ffffff", "GLOW1": "#e3ebfb", "GLOW2": "#d3e0fa", "GLOW3": "#bfd1f6",
}


def palette():
    return LIGHT if theme() == "light" else DARK


def contrast(fg, bg):
    """WCAG contrast ratio between two #rrggbb colors."""
    def lum(c):
        vals = []
        for i in (1, 3, 5):
            v = int(c[i:i + 2], 16) / 255
            vals.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)
