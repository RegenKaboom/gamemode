"""
Game Mode - Main Application with i18n and Theme Support
Supports: English (default), Portuguese (Brazil), Spanish
Theme: Light/Dark/System with persistence
Steam & Epic Games detection
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import threading
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from i18n import get_i18n, set_language, t
from theme_manager import get_theme_manager, Theme
from game_detector import get_game_detector, GameInfo

# App version
APP_VERSION = "2.5.0"
CONFIG_DIR = Path(os.getenv('APPDATA', '')) / 'GameModeLite'
CONFIG_FILE = CONFIG_DIR / 'config.json'
GAMES_CACHE_FILE = CONFIG_DIR / 'detected_games.json'

class Config:
    """Configuration manager with persistence"""

    def __init__(self):
        self.config_dir = CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = CONFIG_FILE
        self.data = self._default_config()
        self.load()

    def _default_config(self) -> Dict[str, Any]:
        return {
            'language': 'en',
            'theme': 'system',
            'font_size': 10,
            'high_contrast': False,
            'reduce_motion': False,
            'screen_reader': False,
            # Game tab
            'cpu_priority': 'high',
            'disable_efficiency': True,
            'power_plan': 'high_performance',
            'auto_apply': True,
            'selected_game': '',
            'custom_games': [],
            # Apps tab
            'lower_bg_priority': True,
            'bg_efficiency_mode': True,
            'low_memory_priority': True,
            'trim_memory': True,
            'trim_interval': 60,
            'excluded_apps': [],
            # Overlay tab
            'overlay_enabled': True,
            'overlay_position': 'top_right',
            'overlay_modules': ['cpu', 'ram', 'ping', 'keys', 'cps', 'crosshair'],
            'fnf_mode': False,
            'fnf_keys': 'dfjk',
            'client_style': False,
            'client_modules': ['cps', 'ping', 'cpu', 'ram', 'game_ram', 'clock', 'session', 'keystrokes'],
            'shader': 'none',
            'opacity': 0.9,
            'scale': 1.0,
            # Brightness tab
            'auto_brightness': False,
            'flash_guard': True,
            'min_brightness': 0.3,
            'max_brightness': 1.0,
            'gamma_ramp': True,
            'magnification_api': False,
            # Network tab
            'qos_enabled': False,
            'dscp_value': 46,
            'prioritize_game': True,
            'tcp_optimize': False,
            # Extras tab
            'update_channel': 'stable',
            'auto_update': True,
        }

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception:
                pass

    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()

    def update(self, data: Dict[str, Any]):
        self.data.update(data)
        self.save()


class GameModeApp:
    """Main Game Mode Application"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = Config()
        self.game_detector = get_game_detector()

        # Initialize i18n and theme
        self.i18n = get_i18n()
        self.i18n.set_language(self.config.get('language', 'en'))

        self.theme_manager = get_theme_manager(self.config_dir)
        self.theme_manager.set_theme(Theme(self.config.get('theme', 'system')))
        self.theme_manager.add_listener(self._on_theme_change)

        # State
        self.detected_games: List[GameInfo] = []
        self.current_game: Optional[GameInfo] = None
        self._refresh_thread: Optional[threading.Thread] = None

        # UI Components
        self.notebook: Optional[ttk.Notebook] = None
        self.tabs: Dict[str, ttk.Frame] = {}
        self.widgets: Dict[str, Any] = {}

        self._setup_window()
        self._create_menu()
        self._create_ui()
        self._apply_theme()
        self._load_detected_games()
        self._start_auto_refresh()

    def _setup_window(self):
        self.root.title(f"{t('app_name')} v{APP_VERSION}")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Set icon if available
        try:
            icon_path = Path(__file__).parent / 'app.ico'
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_menu(self):
        menubar = tk.Menu(self.root)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=t('common.save'), command=self._save_all, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label=t('common.close'), command=self._on_close, accelerator="Alt+F4")
        menubar.add_cascade(label="File", menu=file_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label=t('accessibility_tab.theme') + ": " + t('accessibility_tab.themes.light'),
                            command=lambda: self._set_theme(Theme.LIGHT))
        view_menu.add_command(label=t('accessibility_tab.theme') + ": " + t('accessibility_tab.themes.dark'),
                            command=lambda: self._set_theme(Theme.DARK))
        view_menu.add_command(label=t('accessibility_tab.theme') + ": " + t('accessibility_tab.themes.system'),
                            command=lambda: self._set_theme(Theme.SYSTEM))
        menubar.add_cascade(label="View", menu=view_menu)

        # Language menu
        lang_menu = tk.Menu(menubar, tearoff=0)
        for code, name in [('en', 'English'), ('pt', 'Português (Brasil)'), ('es', 'Español')]:
            lang_menu.add_command(label=name, command=lambda c=code: self._set_language(c))
        menubar.add_cascade(label=t('accessibility_tab.language'), menu=lang_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="GitHub", command=lambda: self._open_url("https://github.com/RegenKaboom/gamemode"))
        help_menu.add_command(label="Issues", command=lambda: self._open_url("https://github.com/RegenKaboom/gamemode/issues"))
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

        # Bind shortcuts
        self.root.bind('<Control-s>', lambda e: self._save_all())

    def _create_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(title_frame, text=f"{t('app_name')} v{APP_VERSION}",
                 font=('Segoe UI', 16, 'bold')).pack(side=tk.LEFT)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self._create_game_tab()
        self._create_apps_tab()
        self._create_overlay_tab()
        self._create_brightness_tab()
        self._create_network_tab()
        self._create_extras_tab()
        self._create_accessibility_tab()

        # Status bar
        self.status_var = tk.StringVar(value=t('common.loading'))
        status_bar = ttk.Label(main_frame, textvariable=self.status_var,
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(10, 0))

    def _create_game_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t('tabs.game'))
        self.tabs['game'] = tab

        # Scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Game optimization section
        section = ttk.LabelFrame(scroll_frame, text=t('game_tab.title'), padding=15)
        section.pack(fill=tk.X, padx=10, pady=10)

        # CPU Priority
        row = ttk.Frame(section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('game_tab.priority_label')).pack(side=tk.LEFT)
        priority_var = tk.StringVar(value=self.config.get('cpu_priority', 'high'))
        self.widgets['cpu_priority'] = priority_var
        combo = ttk.Combobox(row, textvariable=priority_var, values=t('game_tab.priority_options'),
                           state='readonly', width=20)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', lambda e: self.config.set('cpu_priority', priority_var.get()))

        # Efficiency Mode
        eff_var = tk.BooleanVar(value=self.config.get('disable_efficiency', True))
        self.widgets['disable_efficiency'] = eff_var
        ttk.Checkbutton(section, text=t('game_tab.efficiency_mode'), variable=eff_var,
                       command=lambda: self.config.set('disable_efficiency', eff_var.get())).pack(anchor=tk.W, pady=5)

        # Power Plan
        row = ttk.Frame(section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('game_tab.power_plan')).pack(side=tk.LEFT)
        power_var = tk.StringVar(value=self.config.get('power_plan', 'high_performance'))
        self.widgets['power_plan'] = power_var
        combo = ttk.Combobox(row, textvariable=power_var, values=t('game_tab.power_plan_options'),
                           state='readonly', width=20)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', lambda e: self.config.set('power_plan', power_var.get()))

        # Auto Apply
        auto_var = tk.BooleanVar(value=self.config.get('auto_apply', True))
        self.widgets['auto_apply'] = auto_var
        ttk.Checkbutton(section, text=t('game_tab.auto_apply'), variable=auto_var,
                       command=lambda: self.config.set('auto_apply', auto_var.get())).pack(anchor=tk.W, pady=5)

        # Game Selection
        game_section = ttk.LabelFrame(scroll_frame, text=t('game_tab.detected_games'), padding=15)
        game_section.pack(fill=tk.X, padx=10, pady=10)

        # Game list with Steam/Epic tabs
        game_notebook = ttk.Notebook(game_section)
        game_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # All games
        all_frame = ttk.Frame(game_notebook)
        game_notebook.add(all_frame, text="All Games")
        self._create_game_list(all_frame, 'all')

        # Steam games
        steam_frame = ttk.Frame(game_notebook)
        game_notebook.add(steam_frame, text=t('game_tab.steam_games'))
        self._create_game_list(steam_frame, 'steam')

        # Epic games
        epic_frame = ttk.Frame(game_notebook)
        game_notebook.add(epic_frame, text=t('game_tab.epic_games'))
        self._create_game_list(epic_frame, 'epic')

        # Buttons
        btn_frame = ttk.Frame(game_section)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text=t('game_tab.refresh'), command=self._refresh_games).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text=t('game_tab.add_custom'), command=self._add_custom_game).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=t('game_tab.browse'), command=self._browse_game).pack(side=tk.LEFT)

        # Selected game info
        self.widgets['selected_game_label'] = ttk.Label(game_section, text=t('game_tab.game_path') + ": " +
                                                       (self.config.get('selected_game', '') or t('common.info')))
        self.widgets['selected_game_label'].pack(anchor=tk.W, pady=5)

    def _create_game_list(self, parent: ttk.Frame, filter_type: str):
        """Create game list with treeview"""
        columns = ('name', 'source', 'path', 'last_played')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=8)

        tree.heading('name', text=t('steam_epic.game_name'))
        tree.heading('source', text='Source')
        tree.heading('path', text=t('steam_epic.install_path'))
        tree.heading('last_played', text=t('steam_epic.last_played'))

        tree.column('name', width=200)
        tree.column('source', width=80)
        tree.column('path', width=300)
        tree.column('last_played', width=150)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tree.bind('<<TreeviewSelect>>', lambda e: self._on_game_select(tree, filter_type))

        self.widgets[f'game_tree_{filter_type}'] = tree

    def _create_apps_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t('tabs.apps'))
        self.tabs['apps'] = tab

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Background Apps Management
        section = ttk.LabelFrame(scroll_frame, text=t('apps_tab.title'), padding=15)
        section.pack(fill=tk.X, padx=10, pady=10)

        opts = [
            ('lower_bg_priority', t('apps_tab.lower_priority')),
            ('bg_efficiency_mode', t('apps_tab.efficiency_mode')),
            ('low_memory_priority', t('apps_tab.memory_priority')),
            ('trim_memory', t('apps_tab.trim_memory')),
        ]

        for key, label in opts:
            var = tk.BooleanVar(value=self.config.get(key, True))
            self.widgets[key] = var
            ttk.Checkbutton(section, text=label, variable=var,
                           command=lambda k=key, v=var: self.config.set(k, v.get())).pack(anchor=tk.W, pady=3)

        # Trim interval
        row = ttk.Frame(section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('apps_tab.trim_interval')).pack(side=tk.LEFT)
        interval_var = tk.IntVar(value=self.config.get('trim_interval', 60))
        self.widgets['trim_interval'] = interval_var
        spin = ttk.Spinbox(row, from_=10, to=3600, textvariable=interval_var, width=10,
                          command=lambda: self.config.set('trim_interval', interval_var.get()))
        spin.pack(side=tk.RIGHT)

        # Excluded Apps
        excl_section = ttk.LabelFrame(scroll_frame, text=t('apps_tab.excluded_apps'), padding=15)
        excl_section.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        excl_frame = ttk.Frame(excl_section)
        excl_frame.pack(fill=tk.BOTH, expand=True)

        self.widgets['excluded_listbox'] = tk.Listbox(excl_frame, height=6)
        self.widgets['excluded_listbox'].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        excl_scroll = ttk.Scrollbar(excl_frame, command=self.widgets['excluded_listbox'].yview)
        excl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.widgets['excluded_listbox'].configure(yscrollcommand=excl_scroll.set)

        btn_frame = ttk.Frame(excl_section)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text=t('apps_tab.add_exclusion'), command=self._add_exclusion).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text=t('apps_tab.remove_exclusion'), command=self._remove_exclusion).pack(side=tk.LEFT, padx=5)

        self._refresh_excluded_list()

    def _create_overlay_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t('tabs.overlay'))
        self.tabs['overlay'] = tab

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable Overlay
        enable_var = tk.BooleanVar(value=self.config.get('overlay_enabled', True))
        self.widgets['overlay_enabled'] = enable_var
        ttk.Checkbutton(scroll_frame, text=t('overlay_tab.enable'), variable=enable_var,
                       command=lambda: self.config.set('overlay_enabled', enable_var.get())).pack(anchor=tk.W, padx=10, pady=5)

        # Position
        row = ttk.Frame(scroll_frame)
        row.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row, text=t('overlay_tab.position')).pack(side=tk.LEFT)
        pos_var = tk.StringVar(value=self.config.get('overlay_position', 'top_right'))
        self.widgets['overlay_position'] = pos_var
        combo = ttk.Combobox(row, textvariable=pos_var, values=t('overlay_tab.positions'),
                           state='readonly', width=25)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', lambda e: self.config.set('overlay_position', pos_var.get()))

        # Modules
        mod_section = ttk.LabelFrame(scroll_frame, text=t('overlay_tab.modules'), padding=15)
        mod_section.pack(fill=tk.X, padx=10, pady=10)

        self.widgets['overlay_modules'] = {}
        for mod in t('overlay_tab.available_modules'):
            var = tk.BooleanVar(value=mod.lower() in [m.lower() for m in self.config.get('overlay_modules', [])])
            self.widgets['overlay_modules'][mod] = var
            ttk.Checkbutton(mod_section, text=mod, variable=var,
                           command=self._save_overlay_modules).pack(anchor=tk.W, pady=2)

        # FNF Mode
        fnf_section = ttk.LabelFrame(scroll_frame, text=t('overlay_tab.fnf_mode'), padding=15)
        fnf_section.pack(fill=tk.X, padx=10, pady=10)

        fnf_var = tk.BooleanVar(value=self.config.get('fnf_mode', False))
        self.widgets['fnf_mode'] = fnf_var
        ttk.Checkbutton(fnf_section, text=t('overlay_tab.fnf_mode'), variable=fnf_var,
                       command=lambda: self.config.set('fnf_mode', fnf_var.get())).pack(anchor=tk.W, pady=3)

        row = ttk.Frame(fnf_section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('overlay_tab.fnf_keys')).pack(side=tk.LEFT)
        fnf_keys_var = tk.StringVar(value=self.config.get('fnf_keys', 'dfjk'))
        self.widgets['fnf_keys'] = fnf_keys_var
        combo = ttk.Combobox(row, textvariable=fnf_keys_var, values=t('overlay_tab.fnf_presets'),
                           state='readonly', width=15)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', lambda e: self.config.set('fnf_keys', fnf_keys_var.get()))

        # Client Style
        client_section = ttk.LabelFrame(scroll_frame, text=t('overlay_tab.client_style'), padding=15)
        client_section.pack(fill=tk.X, padx=10, pady=10)

        client_var = tk.BooleanVar(value=self.config.get('client_style', False))
        self.widgets['client_style'] = client_var
        ttk.Checkbutton(client_section, text=t('overlay_tab.client_style'), variable=client_var,
                       command=lambda: self.config.set('client_style', client_var.get())).pack(anchor=tk.W, pady=3)

        self.widgets['client_modules'] = {}
        for mod in t('overlay_tab.client_modules'):
            var = tk.BooleanVar(value=mod.lower() in [m.lower() for m in self.config.get('client_modules', [])])
            self.widgets['client_modules'][mod] = var
            ttk.Checkbutton(client_section, text=mod, variable=var,
                           command=self._save_client_modules).pack(anchor=tk.W, pady=2)

        # Shaders
        shader_section = ttk.LabelFrame(scroll_frame, text=t('overlay_tab.shaders'), padding=15)
        shader_section.pack(fill=tk.X, padx=10, pady=10)

        row = ttk.Frame(shader_section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('overlay_tab.shaders')).pack(side=tk.LEFT)
        shader_var = tk.StringVar(value=self.config.get('shader', 'none'))
        self.widgets['shader'] = shader_var
        combo = ttk.Combobox(row, textvariable=shader_var, values=t('overlay_tab.shader_options'),
                           state='readonly', width=20)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', lambda e: self.config.set('shader', shader_var.get()))

        # Opacity & Scale
        for key, label in [('opacity', t('overlay_tab.opacity')), ('scale', t('overlay_tab.scale'))]:
            row = ttk.Frame(scroll_frame)
            row.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(row, text=label).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=self.config.get(key, 0.9 if key == 'opacity' else 1.0))
            self.widgets[key] = var
            scale = ttk.Scale(row, from_=0.1, to=2.0, variable=var, orient=tk.HORIZONTAL,
                             command=lambda v, k=key: self.config.set(k, var.get()))
            scale.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
            val_label = ttk.Label(row, text=f"{var.get():.1f}")
            val_label.pack(side=tk.RIGHT, padx=5)
            var.trace_add('write', lambda *args, l=val_label, v=var: l.config(text=f"{v.get():.1f}"))

    def _create_brightness_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t('tabs.brightness'))
        self.tabs['brightness'] = tab

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        opts = [
            ('auto_brightness', t('brightness_tab.auto_brightness')),
            ('flash_guard', t('brightness_tab.flash_guard')),
            ('gamma_ramp', t('brightness_tab.gamma_ramp')),
            ('magnification_api', t('brightness_tab.magnification_api')),
        ]

        section = ttk.LabelFrame(scroll_frame, text=t('brightness_tab.title'), padding=15)
        section.pack(fill=tk.X, padx=10, pady=10)

        for key, label in opts:
            var = tk.BooleanVar(value=self.config.get(key, True if key == 'flash_guard' else False))
            self.widgets[key] = var
            ttk.Checkbutton(section, text=label, variable=var,
                           command=lambda k=key, v=var: self.config.set(k, v.get())).pack(anchor=tk.W, pady=3)

        # Flash guard description
        ttk.Label(section, text=t('brightness_tab.flash_guard_desc'),
                 font=('Segoe UI', 8), foreground='gray').pack(anchor=tk.W, pady=(0, 10))

        # Min/Max brightness
        for key, label in [('min_brightness', t('brightness_tab.min_brightness')),
                          ('max_brightness', t('brightness_tab.max_brightness'))]:
            row = ttk.Frame(section)
            row.pack(fill=tk.X, pady=5)
            ttk.Label(row, text=label).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=self.config.get(key, 0.3 if key == 'min_brightness' else 1.0))
            self.widgets[key] = var
            scale = ttk.Scale(row, from_=0.0, to=1.0, variable=var, orient=tk.HORIZONTAL,
                             command=lambda v, k=key: self.config.set(k, var.get()))
            scale.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
            val_label = ttk.Label(row, text=f"{var.get():.1f}")
            val_label.pack(side=tk.RIGHT, padx=5)
            var.trace_add('write', lambda *args, l=val_label, v=var: l.config(text=f"{v.get():.1f}"))

    def _create_network_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t('tabs.network'))
        self.tabs['network'] = tab

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        section = ttk.LabelFrame(scroll_frame, text=t('network_tab.title'), padding=15)
        section.pack(fill=tk.X, padx=10, pady=10)

        opts = [
            ('qos_enabled', t('network_tab.qos_enabled')),
            ('prioritize_game', t('network_tab.prioritize_game')),
            ('tcp_optimize', t('network_tab.tcp_optimize')),
        ]

        for key, label in opts:
            var = tk.BooleanVar(value=self.config.get(key, False))
            self.widgets[key] = var
            ttk.Checkbutton(section, text=label, variable=var,
                           command=lambda k=key, v=var: self.config.set(k, v.get())).pack(anchor=tk.W, pady=3)

        # DSCP Value
        row = ttk.Frame(section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('network_tab.dscp_value')).pack(side=tk.LEFT)
        dscp_var = tk.IntVar(value=self.config.get('dscp_value', 46))
        self.widgets['dscp_value'] = dscp_var
        spin = ttk.Spinbox(row, from_=0, to=63, textvariable=dscp_var, width=10,
                          command=lambda: self.config.set('dscp_value', dscp_var.get()))
        spin.pack(side=tk.RIGHT)

        # Flush DNS button
        ttk.Button(section, text=t('network_tab.flush_dns'), command=self._flush_dns).pack(anchor=tk.W, pady=10)

    def _create_extras_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t('tabs.extras'))
        self.tabs['extras'] = tab

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Cleanup
        section = ttk.LabelFrame(scroll_frame, text=t('extras_tab.cleanup'), padding=15)
        section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(section, text=t('extras_tab.scan_junk'), command=self._scan_junk).pack(side=tk.LEFT, padx=5)
        ttk.Button(section, text=t('extras_tab.clean_junk'), command=self._clean_junk).pack(side=tk.LEFT, padx=5)

        # Playtime
        pt_section = ttk.LabelFrame(scroll_frame, text=t('extras_tab.playtime'), padding=15)
        pt_section.pack(fill=tk.X, padx=10, pady=10)

        self.widgets['playtime_today'] = ttk.Label(pt_section, text=f"{t('extras_tab.today')}: 0h")
        self.widgets['playtime_today'].pack(anchor=tk.W)
        self.widgets['playtime_week'] = ttk.Label(pt_section, text=f"{t('extras_tab.this_week')}: 0h")
        self.widgets['playtime_week'].pack(anchor=tk.W)
        self.widgets['playtime_total'] = ttk.Label(pt_section, text=f"{t('extras_tab.total')}: 0h")
        self.widgets['playtime_total'].pack(anchor=tk.W)

        # Game Bar
        gb_section = ttk.LabelFrame(scroll_frame, text=t('extras_tab.game_bar'), padding=15)
        gb_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(gb_section, text=t('extras_tab.disable_game_bar'), command=self._disable_game_bar).pack(side=tk.LEFT, padx=5)
        ttk.Button(gb_section, text=t('extras_tab.restore_game_bar'), command=self._restore_game_bar).pack(side=tk.LEFT, padx=5)

        # Updater
        up_section = ttk.LabelFrame(scroll_frame, text=t('extras_tab.updater'), padding=15)
        up_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(up_section, text=t('extras_tab.check_updates'), command=self._check_updates).pack(side=tk.LEFT, padx=5)

        row = ttk.Frame(up_section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('extras_tab.update_channel')).pack(side=tk.LEFT)
        channel_var = tk.StringVar(value=self.config.get('update_channel', 'stable'))
        self.widgets['update_channel'] = channel_var
        combo = ttk.Combobox(row, textvariable=channel_var, values=t('extras_tab.channels'),
                           state='readonly', width=15)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', lambda e: self.config.set('update_channel', channel_var.get()))

        auto_up_var = tk.BooleanVar(value=self.config.get('auto_update', True))
        self.widgets['auto_update'] = auto_up_var
        ttk.Checkbutton(up_section, text="Auto-check for updates", variable=auto_up_var,
                       command=lambda: self.config.set('auto_update', auto_up_var.get())).pack(anchor=tk.W, pady=5)

    def _create_accessibility_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=t('tabs.accessibility'))
        self.tabs['accessibility'] = tab

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        section = ttk.LabelFrame(scroll_frame, text=t('accessibility_tab.title'), padding=15)
        section.pack(fill=tk.X, padx=10, pady=10)

        # Language
        row = ttk.Frame(section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('accessibility_tab.language')).pack(side=tk.LEFT)
        lang_var = tk.StringVar(value=self.config.get('language', 'en'))
        self.widgets['language'] = lang_var
        lang_names = [f"{v} ({k})" for k, v in t('accessibility_tab.languages').items()]
        combo = ttk.Combobox(row, textvariable=lang_var, values=lang_names, state='readonly', width=25)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', self._on_language_change)

        # Theme
        row = ttk.Frame(section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('accessibility_tab.theme')).pack(side=tk.LEFT)
        theme_var = tk.StringVar(value=self.config.get('theme', 'system'))
        self.widgets['theme'] = theme_var
        theme_names = [f"{self.theme_manager.get_theme_name(k)} ({k})" for k in ['system', 'light', 'dark']]
        combo = ttk.Combobox(row, textvariable=theme_var, values=theme_names, state='readonly', width=25)
        combo.pack(side=tk.RIGHT)
        combo.bind('<<ComboboxSelected>>', self._on_theme_change_combo)

        # Font Size
        row = ttk.Frame(section)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=t('accessibility_tab.font_size')).pack(side=tk.LEFT)
        font_var = tk.IntVar(value=self.config.get('font_size', 10))
        self.widgets['font_size'] = font_var
        spin = ttk.Spinbox(row, from_=8, to=24, textvariable=font_var, width=10,
                          command=lambda: self._apply_font_size(font_var.get()))
        spin.pack(side=tk.RIGHT)

        # Other accessibility options
        for key, label in [
            ('high_contrast', t('accessibility_tab.high_contrast')),
            ('reduce_motion', t('accessibility_tab.reduce_motion')),
            ('screen_reader', t('accessibility_tab.screen_reader')),
        ]:
            var = tk.BooleanVar(value=self.config.get(key, False))
            self.widgets[key] = var
            ttk.Checkbutton(section, text=label, variable=var,
                           command=lambda k=key, v=var: self.config.set(k, v.get())).pack(anchor=tk.W, pady=3)

    def _apply_theme(self):
        """Apply current theme to all widgets"""
        colors = self.theme_manager.get_tkinter_colors()

        # Configure root
        self.root.configure(bg=colors['bg_primary'])

        # Configure ttk styles
        style = ttk.Style()

        # Configure common styles
        style.configure('TFrame', background=colors['bg_primary'])
        style.configure('TLabel', background=colors['bg_primary'], foreground=colors['fg_primary'])
        style.configure('TLabelFrame', background=colors['bg_primary'], foreground=colors['fg_primary'])
        style.configure('TLabelFrame.Label', background=colors['bg_primary'], foreground=colors['fg_primary'])
        style.configure('TButton', background=colors['accent'], foreground='white')
        style.configure('TCheckbutton', background=colors['bg_primary'], foreground=colors['fg_primary'])
        style.configure('TRadiobutton', background=colors['bg_primary'], foreground=colors['fg_primary'])
        style.configure('TCombobox', fieldbackground=colors['input_bg'], background=colors['input_bg'])
        style.configure('TEntry', fieldbackground=colors['input_bg'], foreground=colors['fg_primary'])
        style.configure('TSpinbox', fieldbackground=colors['input_bg'], foreground=colors['fg_primary'])
        style.configure('TNotebook', background=colors['bg_primary'], borderwidth=0)
        style.configure('TNotebook.Tab', background=colors['bg_tertiary'], foreground=colors['fg_primary'],
                       padding=[12, 8])
        style.map('TNotebook.Tab', background=[('selected', colors['accent'])],
                 foreground=[('selected', 'white')])
        style.configure('Treeview', background=colors['input_bg'], foreground=colors['fg_primary'],
                       fieldbackground=colors['input_bg'], borderwidth=0)
        style.configure('Treeview.Heading', background=colors['bg_tertiary'], foreground=colors['fg_primary'])
        style.map('Treeview', background=[('selected', colors['accent'])],
                 foreground=[('selected', 'white')])
        style.configure('Vertical.TScrollbar', background=colors['bg_tertiary'],
                       troughcolor=colors['bg_primary'], borderwidth=0)
        style.configure('Horizontal.TScrollbar', background=colors['bg_tertiary'],
                       troughcolor=colors['bg_primary'], borderwidth=0)
        style.configure('TScale', background=colors['bg_primary'])

        # Update canvas backgrounds
        for widget in self.root.winfo_children():
            self._update_widget_colors(widget, colors)

    def _update_widget_colors(self, widget, colors):
        """Recursively update widget colors"""
        try:
            widget_class = widget.winfo_class()
            if widget_class in ('Canvas', 'Frame', 'LabelFrame'):
                widget.configure(bg=colors['bg_primary'])
            elif widget_class == 'Label':
                widget.configure(bg=colors['bg_primary'], fg=colors['fg_primary'])
            elif widget_class == 'Listbox':
                widget.configure(bg=colors['input_bg'], fg=colors['fg_primary'],
                               selectbackground=colors['accent'], selectforeground='white')
            elif widget_class == 'Text':
                widget.configure(bg=colors['input_bg'], fg=colors['fg_primary'],
                               insertbackground=colors['fg_primary'])
        except Exception:
            pass

        for child in widget.winfo_children():
            self._update_widget_colors(child, colors)

    def _on_theme_change(self, theme: Theme):
        """Callback when theme changes"""
        self.config.set('theme', theme.value)
        self._apply_theme()
        self.status_var.set(t('common.restart_required'))

    def _on_theme_change_combo(self, event):
        """Handle theme change from combobox"""
        value = self.widgets['theme'].get()
        for name in ['system', 'light', 'dark']:
            if name in value.lower():
                self._set_theme(Theme(name))
                break

    def _set_theme(self, theme: Theme):
        """Set theme programmatically"""
        self.theme_manager.set_theme(theme)
        self.widgets['theme'].set(f"{self.theme_manager.get_theme_name(theme.value)} ({theme.value})")

    def _on_language_change(self, event):
        """Handle language change from combobox"""
        value = self.widgets['language'].get()
        for code in ['en', 'pt', 'es']:
            if f"({code})" in value:
                self._set_language(code)
                break

    def _set_language(self, lang: str):
        """Set language programmatically"""
        self.i18n.set_language(lang)
        self.config.set('language', lang)

        # Update UI texts - would need full refresh
        # For now, just show message
        messagebox.showinfo(t('common.info'),
                           t('common.restart_required'))

    def _apply_font_size(self, size: int):
        """Apply font size to all widgets"""
        self.config.set('font_size', size)
        default_font = ('Segoe UI', size)
        self.root.option_add('*Font', default_font)
        # Would need to refresh all widgets for full effect

    def _load_detected_games(self):
        """Load detected games in background"""
        self.status_var.set(t('steam_epic.detecting'))

        def load():
            try:
                games = self.game_detector.detect_all()
                self.detected_games = games
                # Save cache
                self.game_detector.export_to_json(GAMES_CACHE_FILE)
                # Update UI on main thread
                self.root.after(0, self._update_game_lists)
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

        thread = threading.Thread(target=load, daemon=True)
        thread.start()

    def _refresh_games(self):
        """Force refresh game detection"""
        self.status_var.set(t('steam_epic.detecting'))

        def load():
            try:
                games = self.game_detector.detect_all(force_refresh=True)
                self.detected_games = games
                self.game_detector.export_to_json(GAMES_CACHE_FILE)
                self.root.after(0, self._update_game_lists)
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

        thread = threading.Thread(target=load, daemon=True)
        thread.start()

    def _update_game_lists(self):
        """Update all game list treeviews"""
        for filter_type in ['all', 'steam', 'epic']:
            tree = self.widgets.get(f'game_tree_{filter_type}')
            if tree:
                # Clear
                for item in tree.get_children():
                    tree.delete(item)

                # Filter games
                if filter_type == 'all':
                    games = self.detected_games
                elif filter_type == 'steam':
                    games = [g for g in self.detected_games if g.source == 'steam']
                else:
                    games = [g for g in self.detected_games if g.source == 'epic']

                # Populate
                for game in games:
                    last_played = "Never"
                    if game.last_played:
                        last_played = time.strftime('%Y-%m-%d %H:%M', time.localtime(game.last_played))

                    tree.insert('', 'end', values=(
                        game.name,
                        game.source.upper(),
                        game.install_path,
                        last_played
                    ), tags=(game.app_id,))

        self.status_var.set(f"{t('common.success')}: {len(self.detected_games)} games found")

    def _on_game_select(self, tree: ttk.Treeview, filter_type: str):
        """Handle game selection"""
        selection = tree.selection()
        if not selection:
            return

        item = tree.item(selection[0])
        app_id = item['tags'][0] if item['tags'] else None

        for game in self.detected_games:
            if game.app_id == app_id:
                self.current_game = game
                self.config.set('selected_game', game.executable)
                self.widgets['selected_game_label'].config(
                    text=f"{t('game_tab.game_path')}: {game.install_path}/{game.executable}")
                break

    def _add_custom_game(self):
        """Add custom game"""
        path = filedialog.askopenfilename(
            title=t('game_tab.browse'),
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")]
        )
        if path:
            custom_games = self.config.get('custom_games', [])
            custom_games.append(path)
            self.config.set('custom_games', custom_games)
            messagebox.showinfo(t('common.success'), f"Added: {path}")

    def _browse_game(self):
        """Browse for game executable"""
        self._add_custom_game()

    def _refresh_excluded_list(self):
        """Refresh excluded apps listbox"""
        lb = self.widgets.get('excluded_listbox')
        if lb:
            lb.delete(0, tk.END)
            for app in self.config.get('excluded_apps', []):
                lb.insert(tk.END, app)

    def _add_exclusion(self):
        """Add app to exclusion list"""
        path = filedialog.askopenfilename(
            title="Select app to exclude",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")]
        )
        if path:
            excluded = self.config.get('excluded_apps', [])
            if path not in excluded:
                excluded.append(path)
                self.config.set('excluded_apps', excluded)
                self._refresh_excluded_list()

    def _remove_exclusion(self):
        """Remove selected app from exclusion list"""
        lb = self.widgets.get('excluded_listbox')
        if lb:
            selection = lb.curselection()
            if selection:
                excluded = self.config.get('excluded_apps', [])
                if selection[0] < len(excluded):
                    excluded.pop(selection[0])
                    self.config.set('excluded_apps', excluded)
                    self._refresh_excluded_list()

    def _save_overlay_modules(self):
        """Save overlay modules selection"""
        selected = [mod for mod, var in self.widgets['overlay_modules'].items() if var.get()]
        self.config.set('overlay_modules', selected)

    def _save_client_modules(self):
        """Save client style modules selection"""
        selected = [mod for mod, var in self.widgets['client_modules'].items() if var.get()]
        self.config.set('client_modules', selected)

    def _flush_dns(self):
        """Flush DNS cache"""
        import subprocess
        try:
            subprocess.run(['ipconfig', '/flushdns'], check=True, capture_output=True)
            messagebox.showinfo(t('common.success'), "DNS cache flushed")
        except Exception as e:
            messagebox.showerror(t('common.error'), str(e))

    def _scan_junk(self):
        """Scan for junk files"""
        messagebox.showinfo(t('common.info'), "Junk scan feature - implementation needed")

    def _clean_junk(self):
        """Clean junk files"""
        messagebox.showinfo(t('common.info'), "Junk clean feature - implementation needed")

    def _disable_game_bar(self):
        """Disable Xbox Game Bar"""
        messagebox.showinfo(t('common.info'), "Game Bar disable - implementation needed")

    def _restore_game_bar(self):
        """Restore Xbox Game Bar"""
        messagebox.showinfo(t('common.info'), "Game Bar restore - implementation needed")

    def _check_updates(self):
        """Check for updates"""
        messagebox.showinfo(t('common.info'), "Update check - implementation needed")

    def _save_all(self):
        """Save all configuration"""
        self.config.save()
        self.status_var.set(t('common.success'))

    def _open_url(self, url: str):
        """Open URL in browser"""
        import webbrowser
        webbrowser.open(url)

    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About Game Mode",
            f"{t('app_name')} v{APP_VERSION}\n\n"
            f"Game optimizer for Windows\n"
            f"GitHub: https://github.com/RegenKaboom/gamemode\n\n"
            f"Languages: English, Português (Brasil), Español\n"
            f"Themes: Light, Dark, System"
        )

    def _start_auto_refresh(self):
        """Start auto-refresh of games"""
        def refresh():
            while True:
                time.sleep(300)  # 5 minutes
                if self.root.winfo_exists():
                    self.root.after(0, self._load_detected_games)

        thread = threading.Thread(target=refresh, daemon=True)
        thread.start()

    def _on_close(self):
        """Handle window close"""
        self._save_all()
        self.theme_manager.remove_listener(self._on_theme_change)
        self.root.destroy()


def main():
    """Main entry point"""
    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Create root window
    root = tk.Tk()

    # Set DPI awareness for Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # Create app
    app = GameModeApp(root)

    # Run
    root.mainloop()


if __name__ == '__main__':
    main()