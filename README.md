# Game Mode

> A Windows game optimizer with HUD overlay, FNF mode, SOCD cleaner, and Steam/Epic Games detection.  
> Built with Python + Tkinter, compiled with Nuitka, installed via NSIS.

[![Build](https://github.com/RegenKaboom/gamemode/actions/workflows/compilar.yml/badge.svg)](https://github.com/RegenKaboom/gamemode/actions)
[![Release](https://img.shields.io/github/v/release/RegenKaboom/gamemode)](https://github.com/RegenKaboom/gamemode/releases)
[![License](https://img.shields.io/github/license/RegenKaboom/gamemode)](LICENSE)
[![Language](https://img.shields.io/badge/language-Python%20%2B%20Tkinter-blue)](https://www.python.org/)

---

## Features

### Core Optimizer
- **CPU Priority** — Raise game process priority (Normal / High / Real-time)
- **Efficiency Mode** — Disable Windows efficiency mode for maximum boost
- **Power Plan** — Switch to High Performance / Ultimate Performance while gaming
- **Memory Trim** — Return idle memory to system every N seconds
- **Background Apps** — Lower priority, enable efficiency mode, low memory priority for non-game processes

### HUD Overlay
- **Real-time stats**: CPU, RAM, Ping, Keys pressed, CPS, Crosshair, Clock, Session time, Keystrokes
- **Draggable, customizable position** (corners + custom)
- **Opacity & scale** controls

### FNF Mode (Friday Night Funkin')
- 4-lane arrow display that lights up on key press
- KPS (keys per second) counter
- Presets: DFJK, Arrow keys, WASD
- Custom key binding support

### Client-Style Overlay
- Feather / Badlion inspired modular panels
- Modules: CPS, Ping, CPU, RAM, Game RAM, Clock, Session, Keystrokes
- Percentage-based positioning

### Shader Presets
- **Vivid** — Saturated colors
- **Clarity** — Sharp contrast
- **Cinematic** — Film-like tone mapping
- **Sunset** — Warm golden hour
- **Arctic** — Cool blue tones
- **Retro** — CRT/Scanline effect
- **Noir** — High contrast B&W
- **Dream** — Soft bloom/glow

### Brightness Control
- **Auto brightness** based on content
- **Flash Guard** — Instant dim on sudden brightness spikes
- Gamma Ramp / Magnification API backends

### Network Optimization
- **QoS / DSCP marking** for game traffic (requires admin)
- TCP optimizations
- DNS flush utility

### SOCD Cleaner (Simultaneous Opposite Cardinal Directions)
- Resolves conflicting inputs (W+S, A+D) per selected mode:
  - **First** — Earlier key wins
  - **Last** — Later key wins
  - **Neutral** — Both cancelled
- Low-level keyboard hook (`WH_KEYBOARD_LL`)
- Per-game activation (only when game window focused)

### Extra Tools
- **System Cleanup** — Temp files, Roblox logs, crash dumps
- **Playtime Tracker** — Daily/weekly/total per game
- **Xbox Game Bar** — Disable background recording
- **Auto Updater** — GitHub Releases with SHA256 verification

---

## Supported Languages

| Language | Code | Status |
|----------|------|--------|
| English | `en` | ✅ Default |
| Português (Brasil) | `pt` | ✅ Full |
| Español | `es` | ✅ Full |

Language can be selected:
- **During installation** (installer page)
- **In-app** (Accessibility tab)
- **Persisted** across sessions

---

## Themes

| Theme | Description |
|-------|-------------|
| **Light** | Clean light UI |
| **Dark** | Easy on the eyes (default) |
| **System** | Follows Windows setting |

Theme can be selected:
- **During installation** (installer page)
- **In-app** (Accessibility tab)
- **Persisted** across sessions

---

## Steam & Epic Games Detection

Automatically detects installed games from:
- **Steam** — Parses `libraryfolders.vdf` and `appmanifest_*.acf` files
- **Epic Games** — Reads `.item` manifests from `%PROGRAMDATA%\Epic\EpicGamesLauncher\Data\Manifests`

Features:
- Lists all detected games with install path, last played, source
- Filter by platform (All / Steam / Epic)
- Click to select game for optimization
- Add custom games manually
- Auto-refresh every 5 minutes

---

## Installation

### From Releases (Recommended)
1. Go to [Releases](https://github.com/RegenKaboom/gamemode/releases)
2. Download latest `Instalar_GameMode_*.exe`
3. Run installer, choose language & theme
4. Launch Game Mode

### From Source (Development)

**Requirements:**
- Windows 10/11
- Python 3.11+
- NSIS 3.x
- Nuitka

```bash
# Clone
git clone https://github.com/RegenKaboom/gamemode.git
cd gamemode

# Install build dependencies
pip install nuitka ordered-set zstandard

# Compile
python -m nuitka --standalone --windows-console-mode=disable --enable-plugin=tk-inter \
  --include-package=i18n --include-package=theme_manager --include-package=game_detector \
  --include-data-dir=i18n=i18n --output-dir=build --windows-icon-from-ico=app.ico \
  gamemode_app.py

# Build installer
makensis /DAPP_VERSION=2.5.0 GameMode.nsi
```

---

## Project Structure

```
gamemode/
├── gamemode_app.py      # Main application (Tkinter GUI)
├── gm_extras.py         # Extra tools: cleanup, playtime, network, FNF, updater
├── gm_mods.py           # SOCD cleaner (keyboard hook)
├── i18n/                # Internationalization
│   ├── __init__.py      # I18n class + translations loader
│   ├── en.json          # English translations
│   ├── pt.json          # Portuguese (Brazil) translations
│   └── es.json          # Spanish translations
├── theme_manager.py     # Light/Dark/System theme management
├── game_detector.py     # Steam & Epic Games detection
├── GameMode.nsi         # NSIS installer script (multi-language)
├── requirements.txt     # Python dependencies
├── app.ico              # Application icon
├── welcome.bmp          # Installer bitmap
├── novidades.txt        # Changelog (Portuguese)
├── atualizar.txt        # Update info
├── LICENSE              # MIT License
├── README.md            # This file
└── .github/
    └── workflows/
        └── compilar.yml # GitHub Actions: build + release
```

---

## Configuration

All settings stored in `%APPDATA%\GameModeLite\config.json`:

```json
{
  "language": "en",
  "theme": "system",
  "font_size": 10,
  "high_contrast": false,
  "reduce_motion": false,
  "screen_reader": false,
  "cpu_priority": "high",
  "disable_efficiency": true,
  "power_plan": "high_performance",
  "auto_apply": true,
  "selected_game": "",
  "overlay_enabled": true,
  "overlay_position": "top_right",
  "overlay_modules": ["cpu", "ram", "ping", "keys", "cps", "crosshair"],
  "fnf_mode": false,
  "fnf_keys": "dfjk",
  "client_style": false,
  "shader": "none",
  "opacity": 0.9,
  "scale": 1.0,
  "flash_guard": true,
  "qos_enabled": false,
  "update_channel": "stable",
  "auto_update": true
}
```

---

## Building Releases

The GitHub Actions workflow (`.github/workflows/compilar.yml`) handles everything:

1. **Trigger**: Push to `main` or manual dispatch
2. **Compile**: Nuitka creates standalone `.exe`
3. **Install**: NSIS builds installer with language/theme selection
4. **Hash**: SHA256 for `latest.json`
5. **Release**: Creates/updates GitHub Release with installer + `latest.json`

### Manual Release

```bash
# Update version in gamemode_app.py
APP_VERSION = "2.6.0"

# Update changelog
echo "## 2.6.0" > novidades.txt
echo "- New feature X" >> novidades.txt
echo "- Bug fix Y" >> novidades.txt

# Push to main
git add .
git commit -m "Release v2.6.0"
git push origin main
```

The workflow will build and create the release automatically.

---

## Auto-Update System

The app checks `latest.json` on GitHub Releases:
- On startup
- Every 6 hours
- Manual via Extras tab

`latest.json` format:
```json
{
  "version": "2.5.0",
  "url": "https://github.com/RegenKaboom/gamemode/releases/download/v2.5.0/Instalar_GameMode_2.5.0.exe",
  "sha256": "abc123...",
  "notes": "Changelog preview...",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Update channels: **Stable** (default), **Beta**, **Alpha**

---

## Accessibility

- **Screen reader support** (ARIA labels on controls)
- **High contrast mode** (enhanced borders, colors)
- **Reduce motion** (disables animations)
- **Font size** (8–24pt, persisted)
- **Keyboard navigation** (Tab order, shortcuts)
- **Language selection** in installer & app

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing`)
5. Open Pull Request

### Translation Contributions

To add a new language:
1. Copy `i18n/en.json` to `i18n/<code>.json`
2. Translate all strings
3. Add language to `SUPPORTED_LANGS` in `i18n/__init__.py`
4. Add to `LANG_NAMES` and installer `GameMode.nsi`
5. Submit PR

---

## Credits

- **Nuitka** — Python compiler
- **NSIS** — Installer system
- **Tkinter** — GUI framework (stdlib)
- **Windows APIs** — Process, power, input, display management

---

## Links

- **Repository**: https://github.com/RegenKaboom/gamemode
- **Releases**: https://github.com/RegenKaboom/gamemode/releases
- **Issues**: https://github.com/RegenKaboom/gamemode/issues
- **Changelog**: [novidades.txt](novidades.txt)