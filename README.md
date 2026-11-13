# Game Mode

A Windows app that makes games run smoother and shows useful information on screen.

- **Game Mode:** gives the game priority and slows down background apps while you play. Everything is restored when the game closes.
- **Overlays:** CPU, RAM, ping, keys, CPS, crosshair, a Friday Night Funkin' arrow counter and a Feather/Badlion style "Client" look.
- **Profiles:** one profile per game (ping server, overlay look, GPU), with automatic switching.
- **Steam and Epic Games:** Options > *Import from Steam / Epic* finds installed games and adds them as profiles, with the `.exe` path already filled in.
- **Mods tab:** QoS, Movement Helper, brightness, shaders and Windows game tweaks, each with a backup and an Undo button.
- **Languages:** English, Portuguese and Spanish (installer and Options > Accessibility).
- **Look:** side menu, Ctrl+K search, 11 themes (Dark, Light, Midnight, OLED, Ocean, Forest, Violet, Rose, Amber, Emerald, Sakura) and accent colors, in Options > Appearance.
- **Tray icon:** next to the clock, with a right-click menu (open, turn on/off, restore, exit). Closing the window can keep the program in the tray.
- **Update notice:** after every update a window shows what is new (language of your choice).
- **Performance:** Options > *Game Mode's own performance* lowers the program's own CPU use (Normal, Light, Minimal). Games can keep the screen awake and turn off fullscreen optimizations.
- **Automatic updates:** checks GitHub Releases, verifies the SHA-256 of the installer, and keeps your settings.

## Files

| File | What it is |
| --- | --- |
| `gamemode_app.py` | the app (tkinter) |
| `gm_mods.py` | Movement Helper, brightness and shader engines |
| `gm_extras.py` | cleanup, network test, play time, profiles, FNF and Client overlays, updater helpers |
| `gm_i18n.py` | language and theme choice, `tr()` translator, palettes |
| `gm_lang.py` | English and Spanish translation tables (the source texts are Portuguese) |
| `gm_games.py` | Steam and Epic Games detection |
| `gm_tray.py` | icon in the Windows tray (ctypes only) |
| `app.ico` | the program icon (installer, window, tray) |
| `GameMode.nsi` | installer script (English, Portuguese, Spanish; theme page) |
| `compilar.yml` | GitHub Actions workflow (`.github/workflows/`) that builds and publishes a Release |

## Language and theme

Order of choice: what the user picked in Options > Accessibility, then what the installer saved
(`%APPDATA%\GameModeLite\installer_prefs.json`), then the dark theme for older installs that never
chose, then the Windows language and theme.

To add a text, write it in Portuguese in the code and add a row `"texto": ("English", "Español")` to `gm_lang.py`.
A text with no row is shown as written, so a missing translation never breaks the app.

## Build

Pushing to `main` runs the workflow: Nuitka compiles the program, NSIS builds `Instalar_GameMode_<version>.exe`
and a GitHub Release `v<version>` is published with `latest.json`. The version comes from the `APP_VERSION`
line of `gamemode_app.py` (two numbers, like `2.7`). Release notes come from `NOVIDADES.txt`.
See `ATUALIZAR.txt` (Portuguese) for the step-by-step.

The repository must be **public** for installed copies to download updates.
