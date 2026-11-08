"""
Game Mode - Theme Manager
Handles light/dark/system themes with persistence
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from enum import Enum

class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"

class ThemeManager:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(os.getenv('APPDATA', '')) / 'GameModeLite'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'theme_config.json'

        self._theme = Theme.SYSTEM
        self._custom_colors: Dict[str, str] = {}
        self._listeners: list[Callable[[Theme], None]] = []
        self._load_config()

    def _load_config(self):
        """Load theme configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._theme = Theme(data.get('theme', 'system'))
                    self._custom_colors = data.get('custom_colors', {})
            except Exception:
                pass  # Use defaults

    def _save_config(self):
        """Save theme configuration to file"""
        try:
            data = {
                'theme': self._theme.value,
                'custom_colors': self._custom_colors
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Silently fail

    @property
    def theme(self) -> Theme:
        return self._theme

    @property
    def effective_theme(self) -> Theme:
        """Get the actual theme to use (resolves 'system' to light/dark)"""
        if self._theme != Theme.SYSTEM:
            return self._theme

        # Detect system theme on Windows
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
                value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
                return Theme.LIGHT if value == 1 else Theme.DARK
        except Exception:
            return Theme.DARK  # Default to dark

    def set_theme(self, theme: Theme):
        """Set theme and notify listeners"""
        if theme in Theme and theme != self._theme:
            self._theme = theme
            self._save_config()
            self._notify_listeners()

    def set_theme_by_name(self, name: str):
        """Set theme by string name"""
        try:
            self.set_theme(Theme(name.lower()))
        except ValueError:
            pass

    def add_listener(self, callback: Callable[[Theme], None]):
        """Add a theme change listener"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[Theme], None]):
        """Remove a theme change listener"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self):
        """Notify all listeners of theme change"""
        effective = self.effective_theme
        for callback in self._listeners:
            try:
                callback(effective)
            except Exception:
                pass

    def get_colors(self) -> Dict[str, str]:
        """Get color palette for current effective theme"""
        effective = self.effective_theme

        if effective == Theme.DARK:
            base = {
                'bg_primary': '#1a1a1a',
                'bg_secondary': '#2a2a2a',
                'bg_tertiary': '#3a3a3a',
                'fg_primary': '#eeeeee',
                'fg_secondary': '#aaaaaa',
                'fg_muted': '#888888',
                'accent': '#ff9500',
                'accent_hover': '#ffb030',
                'accent_pressed': '#e08000',
                'success': '#0a8d4a',
                'success_hover': '#0da05a',
                'danger': '#cc3333',
                'danger_hover': '#dd4444',
                'border': '#444444',
                'border_focus': '#ff9500',
                'overlay_bg': 'rgba(26, 26, 26, 0.95)',
                'overlay_fg': '#eeeeee',
                'shadow': 'rgba(0, 0, 0, 0.5)',
                'input_bg': '#1a1a1a',
                'input_border': '#444444',
                'hover_bg': '#3a3a3a',
                'disabled_bg': '#2a2a2a',
                'disabled_fg': '#666666',
            }
        else:  # LIGHT
            base = {
                'bg_primary': '#ffffff',
                'bg_secondary': '#f5f5f5',
                'bg_tertiary': '#e8e8e8',
                'fg_primary': '#1a1a1a',
                'fg_secondary': '#555555',
                'fg_muted': '#888888',
                'accent': '#e07000',
                'accent_hover': '#cc6000',
                'accent_pressed': '#b35000',
                'success': '#087038',
                'success_hover': '#0a8040',
                'danger': '#cc3333',
                'danger_hover': '#dd4444',
                'border': '#dddddd',
                'border_focus': '#e07000',
                'overlay_bg': 'rgba(255, 255, 255, 0.95)',
                'overlay_fg': '#1a1a1a',
                'shadow': 'rgba(0, 0, 0, 0.15)',
                'input_bg': '#ffffff',
                'input_border': '#cccccc',
                'hover_bg': '#f0f0f0',
                'disabled_bg': '#f5f5f5',
                'disabled_fg': '#aaaaaa',
            }

        # Merge custom colors
        base.update(self._custom_colors)
        return base

    def get_tkinter_colors(self) -> Dict[str, str]:
        """Get Tkinter-compatible color dict"""
        colors = self.get_colors()
        # Tkinter uses same hex format
        return colors

    def apply_to_tkinter(self, widget, bg_key: str = 'bg_primary', fg_key: str = 'fg_primary'):
        """Apply theme colors to a Tkinter widget"""
        colors = self.get_tkinter_colors()
        try:
            widget.configure(bg=colors[bg_key], fg=colors[fg_key])
        except Exception:
            pass

    def get_stylesheet(self) -> str:
        """Get CSS-like stylesheet for custom widgets"""
        c = self.get_colors()
        return f"""
        * {{
            background-color: {c['bg_primary']};
            color: {c['fg_primary']};
        }}
        .button {{
            background-color: {c['accent']};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }}
        .button:hover {{
            background-color: {c['accent_hover']};
        }}
        .button:pressed {{
            background-color: {c['accent_pressed']};
        }}
        .button.secondary {{
            background-color: {c['bg_tertiary']};
            color: {c['fg_primary']};
        }}
        .input {{
            background-color: {c['input_bg']};
            border: 1px solid {c['input_border']};
            color: {c['fg_primary']};
            padding: 6px 10px;
            border-radius: 4px;
        }}
        .input:focus {{
            border-color: {c['border_focus']};
        }}
        .card {{
            background-color: {c['bg_secondary']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}
        """


# Global instance
_theme_manager: Optional[ThemeManager] = None

def get_theme_manager(config_dir: Optional[Path] = None) -> ThemeManager:
    """Get global theme manager instance"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager(config_dir)
    return _theme_manager