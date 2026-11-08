"""
Game Mode - Steam & Epic Games Detection
Automatically finds installed games from Steam and Epic Games Store
"""

import json
import os
import winreg
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import time

@dataclass
class GameInfo:
    """Information about a detected game"""
    name: str
    install_path: str
    executable: str
    app_id: str
    source: str  # "steam" or "epic"
    last_played: Optional[float] = None
    playtime_hours: float = 0.0
    icon_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameInfo':
        return cls(**data)


class SteamDetector:
    """Detects Steam games from local installation"""

    def __init__(self):
        self.steam_path: Optional[Path] = None
        self.library_folders: List[Path] = []

    def find_steam_path(self) -> Optional[Path]:
        """Find Steam installation path from registry"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                path, _ = winreg.QueryValueEx(key, 'SteamPath')
                return Path(path)
        except Exception:
            pass

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'Software\Valve\Steam') as key:
                path, _ = winreg.QueryValueEx(key, 'SteamPath')
                return Path(path)
        except Exception:
            pass

        # Common default paths
        for path in [
            Path(os.getenv('PROGRAMFILES(X86)', '')) / 'Steam',
            Path(os.getenv('PROGRAMFILES', '')) / 'Steam',
            Path('C:/Program Files (x86)/Steam'),
            Path('C:/Program Files/Steam'),
        ]:
            if path.exists():
                return path

        return None

    def get_library_folders(self) -> List[Path]:
        """Get all Steam library folders from libraryfolders.vdf"""
        folders = []

        if not self.steam_path:
            self.steam_path = self.find_steam_path()

        if not self.steam_path:
            return folders

        # Default steamapps folder
        default_apps = self.steam_path / 'steamapps'
        if default_apps.exists():
            folders.append(default_apps)

        # Parse libraryfolders.vdf for additional libraries
        vdf_path = self.steam_path / 'steamapps' / 'libraryfolders.vdf'
        if vdf_path.exists():
            try:
                content = vdf_path.read_text(encoding='utf-8', errors='ignore')
                # Simple VDF parsing for library folders
                import re
                # Look for "path" entries
                paths = re.findall(r'"path"\s+"([^"]+)"', content)
                for p in paths:
                    lib_path = Path(p) / 'steamapps'
                    if lib_path.exists():
                        folders.append(lib_path)
            except Exception:
                pass

        self.library_folders = folders
        return folders

    def get_acf_files(self) -> List[Path]:
        """Get all appmanifest_*.acf files"""
        acf_files = []
        for lib in self.get_library_folders():
            acf_files.extend(lib.glob('appmanifest_*.acf'))
        return acf_files

    def parse_acf(self, acf_path: Path) -> Optional[GameInfo]:
        """Parse a single appmanifest.acf file"""
        try:
            content = acf_path.read_text(encoding='utf-8', errors='ignore')

            # Simple key-value extraction from VDF
            import re
            data = {}
            for match in re.finditer(r'"([^"]+)"\s+"([^"]*)"', content):
                key, value = match.groups()
                data[key] = value

            name = data.get('name', '')
            app_id = data.get('appid', '')
            install_dir = data.get('installdir', '')

            if not name or not app_id or not install_dir:
                return None

            # Find executable
            game_path = None
            for lib in self.library_folders:
                candidate = lib / 'common' / install_dir
                if candidate.exists():
                    game_path = candidate
                    break

            if not game_path or not game_path.exists():
                return None

            # Find .exe files
            executables = list(game_path.rglob('*.exe'))
            if not executables:
                return None

            # Prefer executable with similar name to game
            main_exe = executables[0]
            for exe in executables:
                if exe.stem.lower() in name.lower() or name.lower() in exe.stem.lower():
                    main_exe = exe
                    break

            # Get last played time from localconfig.vdf
            last_played = self._get_last_played(app_id)

            return GameInfo(
                name=name,
                install_path=str(game_path),
                executable=str(main_exe.relative_to(game_path)),
                app_id=app_id,
                source='steam',
                last_played=last_played,
                playtime_hours=0.0  # Would need Steam API for accurate playtime
            )
        except Exception:
            return None

    def _get_last_played(self, app_id: str) -> Optional[float]:
        """Get last played timestamp from Steam localconfig.vdf"""
        if not self.steam_path:
            return None

        config_path = self.steam_path / 'userdata'
        if not config_path.exists():
            return None

        try:
            for user_dir in config_path.iterdir():
                localconfig = user_dir / 'config' / 'localconfig.vdf'
                if localconfig.exists():
                    content = localconfig.read_text(encoding='utf-8', errors='ignore')
                    # Look for LastPlayed timestamp for this app
                    import re
                    pattern = rf'"{app_id}"\s+\{{[^}}]*"LastPlayed"\s+"(\d+)"'
                    match = re.search(pattern, content)
                    if match:
                        return float(match.group(1))
        except Exception:
            pass

        return None

    def detect_all(self) -> List[GameInfo]:
        """Detect all Steam games"""
        games = []
        self.get_library_folders()  # Initialize

        for acf in self.get_acf_files():
            game = self.parse_acf(acf)
            if game:
                games.append(game)

        # Sort by last played (most recent first)
        games.sort(key=lambda g: g.last_played or 0, reverse=True)
        return games


class EpicGamesDetector:
    """Detects Epic Games from local installation"""

    def __init__(self):
        self.epic_path: Optional[Path] = None
        self.manifests_path: Optional[Path] = None

    def find_epic_path(self) -> Optional[Path]:
        """Find Epic Games installation path"""
        # Check registry
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r'Software\Epic Games\EpicGamesLauncher') as key:
                path, _ = winreg.QueryValueEx(key, 'AppDataPath')
                return Path(path)
        except Exception:
            pass

        # Common paths
        for path in [
            Path(os.getenv('PROGRAMDATA', '')) / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests',
            Path('C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests'),
        ]:
            if path.exists():
                self.manifests_path = path
                # Try to find install location from a manifest
                for mf in path.glob('*.item'):
                    try:
                        data = json.loads(mf.read_text(encoding='utf-8', errors='ignore'))
                        install_loc = data.get('InstallLocation', '')
                        if install_loc:
                            return Path(install_loc).parent
                    except Exception:
                        pass
                return path.parent.parent.parent  # Go up to EpicGamesLauncher

        return None

    def get_manifests(self) -> List[Path]:
        """Get all .item manifest files"""
        if not self.manifests_path:
            self.find_epic_path()

        if self.manifests_path and self.manifests_path.exists():
            return list(self.manifests_path.glob('*.item'))
        return []

    def parse_manifest(self, manifest_path: Path) -> Optional[GameInfo]:
        """Parse an Epic Games .item manifest"""
        try:
            data = json.loads(manifest_path.read_text(encoding='utf-8', errors='ignore'))

            name = data.get('DisplayName', '')
            app_name = data.get('AppName', '')
            install_loc = data.get('InstallLocation', '')
            launch_exe = data.get('LaunchExecutable', '')

            if not name or not install_loc:
                return None

            game_path = Path(install_loc)
            if not game_path.exists():
                return None

            # Find executable
            if launch_exe:
                exe_path = game_path / launch_exe
                if exe_path.exists():
                    executable = launch_exe
                else:
                    # Fallback: find any .exe
                    executables = list(game_path.rglob('*.exe'))
                    executable = str(executables[0].relative_to(game_path)) if executables else ''
            else:
                executables = list(game_path.rglob('*.exe'))
                executable = str(executables[0].relative_to(game_path)) if executables else ''

            if not executable:
                return None

            # Get last played from metadata
            last_played = None
            if 'LastPlayed' in data:
                try:
                    last_played = float(data['LastPlayed'])
                except Exception:
                    pass

            return GameInfo(
                name=name,
                install_path=str(game_path),
                executable=executable,
                app_id=app_name,
                source='epic',
                last_played=last_played,
                playtime_hours=data.get('Playtime', 0) / 3600.0 if 'Playtime' in data else 0.0
            )
        except Exception:
            return None

    def detect_all(self) -> List[GameInfo]:
        """Detect all Epic Games"""
        games = []
        for mf in self.get_manifests():
            game = self.parse_manifest(mf)
            if game:
                games.append(game)

        # Sort by last played
        games.sort(key=lambda g: g.last_played or 0, reverse=True)
        return games


class GameDetector:
    """Combined game detector for Steam and Epic Games"""

    def __init__(self):
        self.steam = SteamDetector()
        self.epic = EpicGamesDetector()
        self._cache: List[GameInfo] = []
        self._cache_time = 0
        self._cache_ttl = 300  # 5 minutes

    def detect_all(self, force_refresh: bool = False) -> List[GameInfo]:
        """Detect all games from both platforms"""
        now = time.time()

        if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        games = []

        try:
            games.extend(self.steam.detect_all())
        except Exception:
            pass

        try:
            games.extend(self.epic.detect_all())
        except Exception:
            pass

        self._cache = games
        self._cache_time = now
        return games

    def get_steam_games(self) -> List[GameInfo]:
        """Get only Steam games"""
        return [g for g in self.detect_all() if g.source == 'steam']

    def get_epic_games(self) -> List[GameInfo]:
        """Get only Epic Games"""
        return [g for g in self.detect_all() if g.source == 'epic']

    def find_game_by_executable(self, exe_path: str) -> Optional[GameInfo]:
        """Find a game by its executable path"""
        exe_path = Path(exe_path).resolve()
        for game in self.detect_all():
            game_exe = Path(game.install_path) / game.executable
            try:
                if game_exe.resolve() == exe_path:
                    return game
            except Exception:
                pass
        return None

    def export_to_json(self, filepath: Path):
        """Export detected games to JSON"""
        games = self.detect_all()
        data = [g.to_dict() for g in games]
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def import_from_json(self, filepath: Path) -> List[GameInfo]:
        """Import games from JSON"""
        if not filepath.exists():
            return []
        data = json.loads(filepath.read_text(encoding='utf-8'))
        self._cache = [GameInfo.from_dict(d) for d in data]
        self._cache_time = time.time()
        return self._cache


# Global instance
_detector: Optional[GameDetector] = None

def get_game_detector() -> GameDetector:
    """Get global game detector instance"""
    global _detector
    if _detector is None:
        _detector = GameDetector()
    return _detector