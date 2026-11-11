"""Finds installed Steam and Epic Games titles by reading the files the launchers already keep.

Nothing here talks to the network, and nothing is written. Every function is safe to call
on a PC without Steam or Epic: it just returns an empty list.
"""
import json
import os
import re
import sys

# Executables that are never "the game": installers, crash reporters, anti-cheat, redistributables.
_IGNORE = re.compile(
    r"(unins|uninstall|setup|install|redist|vcredist|vc_redist|dxsetup|dotnet|crashhandler|"
    r"crashreport|crashpad|unitycrash|easyanticheat|eac|battleye|beservice|cefprocess|"
    r"webhelper|helper|updater|patcher|bootstrap|launcher_helper|ue4prereq|prereq|"
    r"notification_helper|benchmark|configtool|editor)", re.I)


def _read(path):
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def parse_vdf(text):
    """Minimal parser for Valve's key/value format. Returns nested dicts (keys lower-cased)."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    pos = 0

    def block():
        nonlocal pos
        out = {}
        while pos < len(tokens):
            word, brace = tokens[pos]
            pos += 1
            if brace == "}":
                return out
            if brace == "{":
                continue
            key = word.lower()
            if pos < len(tokens) and tokens[pos][1] == "{":
                pos += 1
                out[key] = block()
            elif pos < len(tokens):
                out[key] = tokens[pos][0].replace("\\\\", "\\")
                pos += 1
        return out
    return block()


def pick_exe(folder, hint="", max_depth=3):
    """Best guess for the game's .exe inside a folder. Returns the full path or ''."""
    if not folder or not os.path.isdir(folder):
        return ""
    hint_key = re.sub(r"[^a-z0-9]", "", hint.lower())
    best, best_score = "", -1.0
    base_depth = folder.rstrip("\\/").count(os.sep)
    for root, dirs, files in os.walk(folder):
        depth = root.rstrip("\\/").count(os.sep) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not re.match(r"(_?redist|__installer|directx|dotnet|"
                                                    r"easyanticheat|battleye|crashreport)", d, re.I)]
        for name in files:
            if not name.lower().endswith(".exe") or _IGNORE.search(name):
                continue
            full = os.path.join(root, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            stem = re.sub(r"[^a-z0-9]", "", name[:-4].lower())
            score = min(size / 1e6, 400.0)            # bigger programs are more likely the game
            if hint_key and stem and (stem in hint_key or hint_key in stem):
                score += 1000                          # name matches the game's name
            if "shipping" in name.lower() or "win64" in root.lower():
                score += 30                            # Unreal's real binary
            score -= depth * 5
            if score > best_score:
                best, best_score = full, score
    return best


def steam_roots():
    roots = []
    if sys.platform == "win32":
        try:
            import winreg
            for hive, sub, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam",
                                    "InstallPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, sub) as k:
                        roots.append(str(winreg.QueryValueEx(k, val)[0]))
                except OSError:
                    pass
        except ImportError:
            pass
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(env):
            roots.append(os.path.join(os.environ[env], "Steam"))
    out, seen = [], set()
    for r in roots:
        r = os.path.normpath(r)
        if r.lower() not in seen and os.path.isdir(r):
            seen.add(r.lower())
            out.append(r)
    return out


def steam_libraries(roots):
    libs, seen = [], set()
    for root in roots:
        cands = [root]
        data = parse_vdf(_read(os.path.join(root, "steamapps", "libraryfolders.vdf")))
        folders = data.get("libraryfolders", data)
        if isinstance(folders, dict):
            for v in folders.values():
                if isinstance(v, dict) and v.get("path"):
                    cands.append(v["path"])
                elif isinstance(v, str) and os.path.isabs(v):
                    cands.append(v)
        for c in cands:
            c = os.path.normpath(c)
            if c.lower() not in seen and os.path.isdir(os.path.join(c, "steamapps")):
                seen.add(c.lower())
                libs.append(c)
    return libs


_STEAM_SKIP = re.compile(r"(steamworks|redistributable|proton|steam linux runtime|"
                         r"steamvr|wallpaper engine)", re.I)


def find_steam(roots=None):
    games = []
    libs = steam_libraries(roots if roots is not None else steam_roots())
    for lib in libs:
        apps = os.path.join(lib, "steamapps")
        try:
            names = sorted(os.listdir(apps))
        except OSError:
            continue
        for fn in names:
            if not (fn.startswith("appmanifest_") and fn.endswith(".acf")):
                continue
            state = parse_vdf(_read(os.path.join(apps, fn))).get("appstate", {})
            name, folder = state.get("name", ""), state.get("installdir", "")
            if not name or not folder or _STEAM_SKIP.search(name):
                continue
            exe = pick_exe(os.path.join(apps, "common", folder), name)
            if exe:
                games.append({"name": name, "exe": os.path.basename(exe), "path": exe,
                              "source": "Steam"})
    return games


def find_epic(manifests_dir=None):
    games = []
    folder = manifests_dir or os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                                           "Epic", "EpicGamesLauncher", "Data", "Manifests")
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return games
    for fn in names:
        if not fn.lower().endswith(".item"):
            continue
        try:
            item = json.loads(_read(os.path.join(folder, fn)))
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        name, loc = item.get("DisplayName", ""), item.get("InstallLocation", "")
        launch = item.get("LaunchExecutable", "")
        if not name or not loc or item.get("bIsApplication") is False:
            continue
        exe = ""
        if launch and not _IGNORE.search(launch):
            cand = os.path.join(loc, launch.replace("/", os.sep))
            if os.path.isfile(cand):
                exe = cand
        exe = exe or pick_exe(loc, name)
        if exe:
            games.append({"name": name, "exe": os.path.basename(exe), "path": exe,
                          "source": "Epic"})
    return games


def find_games(steam_roots_=None, epic_dir=None):
    """All games found, sorted by name, one entry per .exe name."""
    found, seen = [], set()
    for g in find_steam(steam_roots_) + find_epic(epic_dir):
        key = g["exe"].lower()
        if key not in seen:
            seen.add(key)
            found.append(g)
    return sorted(found, key=lambda g: g["name"].lower())
