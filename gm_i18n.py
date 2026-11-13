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
THEME_NAMES = ("dark", "light", "midnight", "oled", "ocean", "forest", "violet", "rose", "amber",
               "emerald", "sakura")
LIGHT_THEMES = ("light", "sakura")
THEME_CHOICES = ("auto",) + THEME_NAMES
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


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    """Blend color a toward color b by t (0 = a, 1 = b)."""
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


def is_light(name=None):
    return (name or theme()) in LIGHT_THEMES


def _build(bg, side, surface, accent, accent2, text, muted, border, light=False):
    """Every color the program uses, from the few 'tokens' a theme is made of."""
    black = "#000000"
    return {
        "BG": bg, "SIDE": side, "CARD": surface, "PANEL": mix(surface, text, 0.08), "BORDER": border,
        "TEXT": text, "MUTED": muted, "ACCENT": accent,
        "GREEN": "#0f7a44" if light else "#35d07f", "WARN": "#a85a00" if light else "#f5a623",
        "PINK": accent2, "TEAL": "#0b7a70" if light else "#2ec4b6",
        "SEL": mix(surface, accent, 0.28 if not light else 0.22),
        "ACCENT_HOVER": mix(accent, black, 0.18),
        "OFF": mix(surface, text, 0.28 if light else 0.22), "OFF_DIS": mix(surface, text, 0.12),
        "KNOB_DIS": mix(surface, "#ffffff" if light else text, 0.6 if light else 0.45),
        "ICON": muted, "ICON_HOVER": text, "ICON_BG": mix(surface, accent, 0.22),
        "BTN_BG": surface if light else mix(bg, black, 0.3),
        "GLOW1": mix(bg, accent, 0.14), "GLOW2": mix(bg, accent, 0.24), "GLOW3": mix(bg, accent, 0.36),
    }


# name: (bg, sidebar, surface/cards, accent, secondary accent, text, muted text, border)
_TOKENS = {
    "midnight": ("#0b1020", "#0e1426", "#141b30", "#6f8cff", "#b07cff", "#e6e9f5", "#8f98b5", "#232c47"),
    "oled": ("#000000", "#060606", "#0e0e10", "#5b9dff", "#7c6cff", "#f2f2f2", "#9a9aa3", "#1d1d21"),
    "ocean": ("#0a1a24", "#0d212d", "#112a38", "#2ec4d6", "#4f8cff", "#e4f2f7", "#86a7b5", "#1e3b4b"),
    "forest": ("#0e1a14", "#112019", "#162a20", "#3fcf8e", "#c9d65a", "#e5f2ea", "#8caa98", "#23402f"),
    "violet": ("#130f1f", "#181328", "#1e1830", "#9b7bff", "#e879f9", "#ece8f8", "#9a92b8", "#2d2547"),
    "rose": ("#1a0f14", "#20131a", "#281820", "#f06292", "#ff9e80", "#f6e8ee", "#b8939f", "#3a2430"),
    "amber": ("#18130b", "#1e170d", "#261d10", "#f5a623", "#ff7043", "#f4ecde", "#b09f80", "#3a2d18"),
    "emerald": ("#0b1713", "#0e1d18", "#12261f", "#2fd18a", "#36c2d8", "#e3f3ec", "#86a899", "#1f3d32"),
}
_TOKENS_LIGHT = {
    "sakura": ("#fdf4f7", "#f9e9ef", "#ffffff", "#b83a74", "#7d4ec4", "#2a1b22", "#6f4f5e", "#e8cdd8"),
}

# colors offered as the accent of any theme (None = the theme's own)
ACCENT_CHOICES = ("", "#4f8cff", "#8b6cf5", "#ee5fa0", "#f05d5e", "#f0a030", "#3ecf8e", "#22b8cf")


def fit_accent(accent, bg, light):
    """Moves an accent color just enough to stay readable on the theme (white button text, text on bg)."""
    for _ in range(14):
        if light:
            ok = contrast("#ffffff", accent) >= 4.5 and contrast(accent, bg) >= 4.5
            if ok:
                break
            accent = mix(accent, "#000000", 0.08)
        else:
            ok = contrast(accent, bg) >= 4.5
            if ok or contrast("#ffffff", accent) <= 3.1:
                break
            accent = mix(accent, "#ffffff", 0.08)
    return accent


def accent_choice():
    """The accent the person picked ('' = the theme's own)."""
    saved = _load_json(SETTINGS_PATH) or {}
    ui = saved.get("ui") if isinstance(saved.get("ui"), dict) else {}
    value = ui.get("accent", "")
    return value if value in ACCENT_CHOICES else ""


def palette_for(name, accent=""):
    light = is_light(name)
    if name == "dark":
        pal = dict(DARK)
    elif name == "light":
        pal = dict(LIGHT)
    elif name in _TOKENS or name in _TOKENS_LIGHT:
        pal = _build(*(_TOKENS.get(name) or _TOKENS_LIGHT[name]), light=light)
    else:
        pal = dict(DARK)
    if accent:
        acc = fit_accent(accent, pal["BG"], light)
        pal.update(ACCENT=acc, ACCENT_HOVER=mix(acc, "#000000", 0.18),
                   SEL=mix(pal["CARD"], acc, 0.28 if not light else 0.22),
                   ICON_BG=mix(pal["CARD"], acc, 0.22), GLOW1=mix(pal["BG"], acc, 0.14),
                   GLOW2=mix(pal["BG"], acc, 0.24), GLOW3=mix(pal["BG"], acc, 0.36))
    # text on top of an accent-colored button: white or near-black, whichever reads better
    pal["ON_ACCENT"] = "#ffffff" if contrast("#ffffff", pal["ACCENT"]) >= contrast("#101114", pal["ACCENT"]) \
        else "#101114"
    return pal


def palette():
    return palette_for(theme(), accent_choice())


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
