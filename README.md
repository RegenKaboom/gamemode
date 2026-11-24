# Game Mode

A Windows app that makes games run smoother and shows useful information on screen.

- **Game Mode:** gives the game priority and slows down background apps while you play. Everything is restored when the game closes.
- **Overlays:** CPU, RAM, ping, keys, CPS, crosshair, a Friday Night Funkin' arrow counter and a Feather/Badlion style "Client" look.
- **Profiles:** one profile per game (ping server, overlay look, GPU), with automatic switching.
- **Steam and Epic Games:** Options > *Import from Steam / Epic* finds installed games and adds them as profiles, with the `.exe` path already filled in.
- **Mods tab:** QoS, Movement Helper, brightness, shaders, Windows game tweaks, hardware-accelerated GPU scheduling (HAGS), background services (SysMain/Superfetch + Windows Search), system & privacy tweaks (telemetry, consumer features, experimentation, Delivery Optimization, voice activation, settings sync, Win32 Priority, service-split threshold), background Task Scheduler tasks, power & disk (hibernation, USB selective suspend, TRIM), Windows Game Mode, mouse acceleration off, keyboard without popups, Windows nudges, Media Player tracking, search suggestions/cloud search, shader cache cleanup, monitor refresh rate and Windows startup programs. Everything that changes Windows keeps a backup and has an Undo button (the shader cache is just rebuilt by the games).
- **Languages:** English, Portuguese and Spanish (installer and Options > Accessibility).
- **Look:** rounded cards and buttons, side menu, Ctrl+K search, 11 themes (Dark, Light, Midnight, OLED, Ocean, Forest, Violet, Rose, Amber, Emerald, Sakura) and accent colors, in Options > Appearance.
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
line of `gamemode_app.py` (two numbers, like `2.9`). Release notes come from `NOVIDADES.txt`.
See `ATUALIZAR.txt` (Portuguese) for the step-by-step.

The repository must be **public** for installed copies to download updates.

Nuitka's `--standalone` mode bundles its own copy of the Python interpreter and every module the
program needs (including Tkinter, via `--enable-plugin=tk-inter`) inside `GameMode.exe`'s folder.
Installed copies never call out to a system Python and never require one to be installed — the
`Python: ...` line Options > *Copiar diagnóstico* shows is just the version used to build that
release, for troubleshooting.

## Administrator mode

The app runs normally without administrator rights; a few actions elevate just that one action
through a small `--admin-job` helper process (see `run_admin_job` / `admin_job_main`), so Windows
only asks for permission for those. Each admin job is a fixed, hardcoded task — never PowerShell,
never a path or service name coming from outside the program — to keep the elevated surface as
small as possible:

| job | does |
| --- | --- |
| `tweaks` | the 6 `WIN_TWEAKS` registry values ("Windows para jogos") |
| `hags` | the single `HwSchedMode` registry value (hardware-accelerated GPU scheduling) |
| `svc_off` / `svc_on` | stops/starts the two `BG_SERVICES` (SysMain, WSearch) via `sc.exe` |
| `debloat` | the 10 `DEBLOAT_TWEAKS` registry values (telemetry, consumer features, experimentation, Delivery Optimization, voice activation, settings sync, Win32 Priority, service-split threshold, deferred updates) |
| `tasks_off` / `tasks_on` | disables/enables the 5 `TASK_PATHS` scheduled tasks via `schtasks.exe` |
| `power_off` / `power_on` | hibernation, USB selective suspend and TRIM via `powercfg.exe` / `fsutil.exe` |

On first open (if not already elevated) the app offers, once, to always reopen as administrator
instead — this avoids the repeated per-action prompts, at the cost of a UAC prompt on every launch.
That choice is `start_as_admin` in `settings.json` and can be changed any time in Options.
