"""
gm_extras.py - extras do Game Mode (sem nada que dependa do Windows para importar).

  Limpeza de temporários: acha e apaga arquivos velhos de pastas de lixo.
  Rede: teste de conexão (tempo, variação, perda) e limpar cache de DNS.
  Tempo de jogo: soma segundos por dia e guarda num arquivo.
"""

import json
import os
import re
import socket
import subprocess
import time

CREATE_NO_WINDOW = 0x08000000
REPARSE = 0x400  # junção/link no Windows: nunca entra nessas pastas


# ------------------------------------------------------------------ texto
def human_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def fmt_hm(seconds):
    minutes = int(seconds // 60)
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}min" if h else f"{m}min"


# --------------------------------------------------------- limpeza de lixo
def junk_roots():
    """[(nome, pasta)] das pastas que podem ser limpas. Só as que existem."""
    env = os.environ
    cands = [
        ("Temp do usuário", env.get("TEMP") or env.get("TMP") or ""),
        ("Temp do Windows", os.path.join(env.get("SystemRoot", ""), "Temp") if env.get("SystemRoot") else ""),
        ("Logs do Roblox", os.path.join(env.get("LOCALAPPDATA", ""), "Roblox", "logs")
         if env.get("LOCALAPPDATA") else ""),
        ("Relatórios de erro", os.path.join(env.get("LOCALAPPDATA", ""), "CrashDumps")
         if env.get("LOCALAPPDATA") else ""),
    ]
    seen, out = set(), []
    for label, path in cands:
        if path and os.path.isdir(path) and os.path.realpath(path).lower() not in seen:
            seen.add(os.path.realpath(path).lower())
            out.append((label, path))
    return out


def _is_link(path):
    try:
        st = os.lstat(path)
    except OSError:
        return True
    if os.path.islink(path):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & REPARSE)


def scan_junk(roots, min_age_hours=24, now=None):
    """Procura arquivos mais velhos que min_age_hours. Não apaga nada.
    Retorna {"files": [(caminho, tamanho)], "dirs": [pastas], "by": {nome: (qtd, bytes)}}."""
    now = now or time.time()
    cutoff = now - min_age_hours * 3600
    files, dirs, by = [], [], {}
    for label, root in roots:
        count = size = 0
        for cur, subdirs, names in os.walk(root, topdown=True, followlinks=False):
            subdirs[:] = [d for d in subdirs if not _is_link(os.path.join(cur, d))]
            if cur != root:
                dirs.append(cur)
            for name in names:
                path = os.path.join(cur, name)
                try:
                    if _is_link(path):
                        continue
                    st = os.lstat(path)
                    if st.st_mtime > cutoff:
                        continue
                    files.append((path, st.st_size))
                    count += 1
                    size += st.st_size
                except OSError:
                    continue
        by[label] = (count, size)
    return {"files": files, "dirs": dirs, "by": by}


def delete_junk(scan):
    """Apaga o que o scan achou. Retorna (bytes_liberados, apagados, ficaram)."""
    freed = done = failed = 0
    for path, size in scan["files"]:
        try:
            try:
                os.remove(path)
            except PermissionError:
                os.chmod(path, 0o666)  # tira o "somente leitura" e tenta de novo
                os.remove(path)
            freed += size
            done += 1
        except OSError:
            failed += 1  # em uso ou sem permissão: fica
    for d in sorted(scan["dirs"], key=len, reverse=True):
        try:
            os.rmdir(d)  # só apaga se ficou vazia
        except OSError:
            pass
    return freed, done, failed


# ------------------------------------------------------------------- rede
def tcp_probe(host, port=443, count=8, timeout=2.0):
    """Mede o tempo de abrir conexão com o host. Retorna dict ou None se host vazio."""
    host = (host or "").strip()
    if not host:
        return None
    times, lost = [], 0
    for i in range(count):
        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                pass
            times.append((time.perf_counter() - t0) * 1000)
        except OSError:
            lost += 1
        if i < count - 1:
            time.sleep(0.2)
    res = {"host": host, "sent": count, "lost": lost, "min": 0.0, "avg": 0.0, "max": 0.0, "jitter": 0.0}
    if times:
        res["min"], res["max"] = min(times), max(times)
        res["avg"] = sum(times) / len(times)
        if len(times) > 1:
            res["jitter"] = sum(abs(a - b) for a, b in zip(times, times[1:])) / (len(times) - 1)
    return res


def flush_dns():
    try:
        r = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Não consegui rodar: {exc}"
    if r.returncode == 0:
        return True, "Cache de DNS limpo."
    return False, "O Windows recusou. Abra o Game Mode como administrador para limpar o DNS."


# ------------------------------------------------------------ tempo de jogo
def load_playtime(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        days = data.get("days", {})
        if isinstance(days, dict):
            return {"days": {str(k): float(v) for k, v in days.items() if isinstance(v, (int, float))}}
    except (OSError, ValueError, AttributeError):
        pass
    return {"days": {}}


def save_playtime(path, data, keep_days=120):
    days = data["days"]
    for old in sorted(days)[:-keep_days]:
        days.pop(old, None)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        pass


def add_seconds(data, seconds, when=None):
    day = time.strftime("%Y-%m-%d", time.localtime(when or time.time()))
    data["days"][day] = data["days"].get(day, 0.0) + max(0.0, seconds)


def playtime_summary(data, when=None):
    """(hoje, últimos 7 dias, total) em segundos."""
    when = when or time.time()
    today = time.strftime("%Y-%m-%d", time.localtime(when))
    week_days = {time.strftime("%Y-%m-%d", time.localtime(when - i * 86400)) for i in range(7)}
    days = data["days"]
    return days.get(today, 0.0), sum(v for k, v in days.items() if k in week_days), sum(days.values())


# ------------------------------------------------------- Friday Night Funkin'
from collections import deque

FNF_COLORS = ["#c24b99", "#00ffff", "#12fa05", "#f9393f"]   # esquerda, baixo, cima, direita
FNF_DIRS = ["left", "down", "up", "right"]
FNF_PRESETS = {                                   # ordem: esquerda, baixo, cima, direita
    "dfjk": ("D", "F", "J", "K"),
    "arrows": ("LEFT", "DOWN", "UP", "RIGHT"),
    "wasd": ("A", "S", "W", "D"),
}
FNF_ARROW_LABEL = {"LEFT": "\u2190", "DOWN": "\u2193", "UP": "\u2191", "RIGHT": "\u2192"}
HOTKEY_VK = {"f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79}

_NAMED = {"up": 0x26, "cima": 0x26, "down": 0x28, "baixo": 0x28, "left": 0x25,
          "esquerda": 0x25, "right": 0x27, "direita": 0x27,
          "\u2191": 0x26, "\u2193": 0x28, "\u2190": 0x25, "\u2192": 0x27}


def parse_vk(text):
    """'d', '5', 'f3', 'cima' -> código da tecla. None se não entendi."""
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in _NAMED:
        return _NAMED[t]
    if len(t) == 1 and ("a" <= t <= "z" or "0" <= t <= "9"):
        return ord(t.upper())
    if t[0] == "f" and t[1:].isdigit() and 1 <= int(t[1:]) <= 24:
        return 0x70 + int(t[1:]) - 1
    return None


def fnf_keys(preset, custom):
    """(códigos, rótulos) das 4 colunas. ([], []) se as teclas não servem."""
    names = FNF_PRESETS.get(preset)
    if names is None:                              # personalizado
        names = tuple(str(c).strip() for c in (list(custom) + [""] * 4)[:4])
    vks = [parse_vk(n) for n in names]
    if None in vks or len(set(vks)) != 4:
        return [], []
    labels = [FNF_ARROW_LABEL.get(n.upper(), n.upper()) for n in names]
    return vks, labels


def arrow_points(direction, cx, cy, r):
    """Polígono de uma seta (left/down/up/right) centrada em (cx, cy), raio r."""
    base = [(0, -1), (0.9, -0.05), (0.38, -0.05), (0.38, 0.9), (-0.38, 0.9), (-0.38, -0.05), (-0.9, -0.05)]
    rot = {"up": lambda x, y: (x, y), "right": lambda x, y: (-y, x),
           "down": lambda x, y: (-x, -y), "left": lambda x, y: (y, -x)}[direction]
    pts = []
    for x, y in base:
        rx, ry = rot(x, y)
        pts += [cx + rx * r, cy + ry * r]
    return pts


class LaneCounter:
    """Conta apertos das 4 colunas: por coluna, total, KPS (últimos 1 s) e pico."""

    def __init__(self):
        self.down = [False] * 4
        self.count = [0] * 4
        self.total = 0
        self.peak = 0
        self.times = deque()
        self.last_press = None
        self.auto_reset_s = 0          # 0 = desligado

    def reset(self):
        self.count = [0] * 4
        self.total = 0
        self.peak = 0
        self.times.clear()

    def update(self, now, pressed):
        for i, p in enumerate(pressed[:4]):
            if p and not self.down[i]:
                if (self.auto_reset_s and self.last_press is not None and self.total
                        and now - self.last_press > self.auto_reset_s):
                    self.reset()               # música nova: começa do zero
                self.count[i] += 1
                self.total += 1
                self.times.append(now)
                self.last_press = now
            self.down[i] = bool(p)
        while self.times and now - self.times[0] > 1.0:
            self.times.popleft()
        if len(self.times) > self.peak:
            self.peak = len(self.times)

    def kps(self):
        return len(self.times)


# ------------------------------------------------------- perfis de jogo
PROFILE_KEYS = ("exe", "name", "ping_host", "gpu", "look", "path")


def normalize_exe(text):
    """' "C:\\x\\Funkin.EXE" ' -> 'Funkin.EXE' (nome do arquivo, com .exe). '' se vazio."""
    t = str(text or "").strip().strip('"').strip("'").strip()
    t = t.replace("/", "\\").rsplit("\\", 1)[-1].strip()
    if not t:
        return ""
    return t if t.lower().endswith(".exe") else t + ".exe"


def new_profile(exe, name=None, ping_host="", gpu=False, look="Classic", path=""):
    exe = normalize_exe(exe)
    return {"exe": exe, "name": (name or "").strip() or (exe[:-4].title() if exe else "Novo jogo"),
            "ping_host": str(ping_host or "").strip(), "gpu": bool(gpu),
            "look": look or "Classic", "path": str(path or "")}


def find_profile(profiles, exe):
    want = (exe or "").lower()
    for p in profiles or []:
        if p.get("exe", "").lower() == want:
            return p
    return None


def clean_profiles(raw, valid_looks=None):
    """Arruma a lista vinda do arquivo: tira o que não é perfil, completa campos, tira repetidos."""
    out, seen = [], set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        exe = normalize_exe(item.get("exe"))
        if not exe or exe.lower() in seen:
            continue
        seen.add(exe.lower())
        look = item.get("look")
        if not isinstance(look, str) or (valid_looks is not None and look not in valid_looks):
            look = "Classic"
        out.append(new_profile(exe, item.get("name"), item.get("ping_host"), item.get("gpu"),
                               look, item.get("path")))
    return out


def pick_running(profiles, current_exe, running_names):
    """Perfil para onde trocar: só se o jogo atual NÃO está aberto e outro jogo da lista está."""
    running = {str(n).lower() for n in running_names}
    if (current_exe or "").lower() in running:
        return None
    for p in profiles or []:
        if p.get("exe", "").lower() in running:
            return p
    return None


# ------------------------------------------------ visual "Client" (Feather/Badlion)
CLIENT_TEXT_MODULES = [("cps", "CPS"), ("ping", "Ping"), ("cpu", "CPU"), ("ram", "RAM do PC"),
                       ("gmem", "RAM do jogo"), ("clock", "Relógio"), ("session", "Tempo de sessão")]
CLIENT_MODULES = CLIENT_TEXT_MODULES + [("keys", "Teclas e mouse")]


def client_defaults():
    """Configuração plana: <módulo>_on, _x, _y (x e y em % da tela livre: 0 = canto, 100 = outro canto)."""
    cfg = {"style": "dark", "accent": "cyan",
           "keys_space": True, "keys_mouse": True, "keys_mods": False, "keys_cps": True}
    for i, (key, _label) in enumerate(CLIENT_TEXT_MODULES):
        cfg[f"{key}_on"] = key in ("cps", "ping", "cpu", "ram", "gmem")
        cfg[f"{key}_x"] = 0
        cfg[f"{key}_y"] = 1 + 3 * i
    cfg["keys_on"] = True
    cfg["keys_x"] = 0
    cfg["keys_y"] = 100
    return cfg


def fmt_clock(seconds):
    s = int(max(0, seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}"


def module_parts(key, cps=(0, 0), ping=None, cpu=0.0, ram=0.0, gmem_mb=0.0, session_s=0, clock=""):
    """(rótulo, valor) de cada módulo de texto."""
    if key == "cps":
        return "CPS", f"{cps[0]} | {cps[1]}"
    if key == "ping":
        return "PING", "--" if ping is None else f"{ping:.0f} ms"
    if key == "cpu":
        return "CPU", f"{cpu:.0f}%"
    if key == "ram":
        return "RAM", f"{ram:.0f}%"
    if key == "gmem":
        if gmem_mb <= 0:
            return "RAM JOGO", "--"
        return "RAM JOGO", f"{gmem_mb / 1024:.1f} GB" if gmem_mb >= 1024 else f"{gmem_mb:.0f} MB"
    if key == "clock":
        return "", clock
    if key == "session":
        return "SESSÃO", fmt_clock(session_s) if session_s else "--"
    return "", ""


def anchor_xy(sw, sh, w, h, x_pct, y_pct, margin=8):
    """Canto de cima-esquerda de uma caixa w x h. 0% = encostada no começo, 100% = no fim. Nunca sai da tela."""
    free_x = max(0, sw - w - 2 * margin)
    free_y = max(0, sh - h - 2 * margin)
    x = margin + free_x * max(0, min(100, x_pct)) / 100.0
    y = margin + free_y * max(0, min(100, y_pct)) / 100.0
    return x, y


def keystroke_layout(s, gap, space=True, mouse=True, mods=False):
    """Retângulos (rótulo, x, y, w, h) das teclas no estilo Feather. Retorna (lista, largura, altura)."""
    width = 3 * s + 2 * gap
    half = (width - gap) / 2
    rects = [("W", s + gap, 0, s, s), ("A", 0, s + gap, s, s), ("S", s + gap, s + gap, s, s),
             ("D", 2 * (s + gap), s + gap, s, s)]
    y = 2 * (s + gap)
    if mouse:
        rects += [("LMB", 0, y, half, s), ("RMB", half + gap, y, half, s)]
        y += s + gap
    if mods:
        h = s * 0.7
        rects += [("SHIFT", 0, y, half, h), ("CTRL", half + gap, y, half, h)]
        y += h + gap
    if space:
        h = s * 0.6
        rects.append(("SPACE", 0, y, width, h))
        y += h + gap
    return rects, width, y - gap


# ---------------------------------------------------- Xbox Game Bar (gravação em 2º plano)
GAMEBAR_VALUES = [
    (r"System\GameConfigStore", "GameDVR_Enabled"),
    (r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled"),
    (r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled"),
]


def _gb_id(path, name):
    return f"{path}|{name}"


def gamebar_read():
    """{'caminho|nome': valor ou None} (só o seu usuário, sem administrador)."""
    import winreg
    out = {}
    for path, name in GAMEBAR_VALUES:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                out[_gb_id(path, name)] = winreg.QueryValueEx(key, name)[0]
        except OSError:
            out[_gb_id(path, name)] = None
    return out


def gamebar_is_off():
    try:
        return all(v == 0 for v in gamebar_read().values())
    except Exception:
        return False


def gamebar_off():
    """Desliga a gravação em segundo plano. Retorna o que havia antes (para desfazer)."""
    import winreg
    before = gamebar_read()
    for path, name in GAMEBAR_VALUES:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 0)
    return before


def gamebar_restore(before):
    """Volta ao que estava. Valor que não existia antes é apagado."""
    import winreg
    for path, name in GAMEBAR_VALUES:
        old = before.get(_gb_id(path, name))
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                if old is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except OSError:
                        pass
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(old))
        except OSError:
            pass


# ------------------------------------------------------------- atualização automática
import hashlib
import urllib.request

MAX_MANIFEST = 200_000
MAX_INSTALLER = 300 * 1024 * 1024


def parse_version(text):
    """'2.3', 'v2.3' ou '2.3 (texto)' -> (2, 3). Sem número -> (0,)."""
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", str(text or ""))
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def _norm(parts):
    parts = list(parts)
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer(remote, local):
    return _norm(parse_version(remote)) > _norm(parse_version(local))


def installer_url(repo, version):
    return f"https://github.com/{repo}/releases/download/v{version}/Instalar_GameMode_{version}.exe"


def validate_manifest(data, repo):
    """Aceita só o formato esperado, com o endereço exato do instalador no GitHub do projeto."""
    if not isinstance(data, dict):
        return None
    version = str(data.get("version", "")).strip()
    url = str(data.get("url", "")).strip()
    sha = str(data.get("sha256", "")).strip().lower()
    if not re.fullmatch(r"\d+(\.\d+){0,3}", version) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return None
    if url != installer_url(repo, version):
        return None
    return {"version": version, "url": url, "sha256": sha, "notes": str(data.get("notes", ""))[:800]}


def fetch_manifest(url, repo, opener=None, timeout=10):
    """Baixa e confere o latest.json. None se der qualquer problema."""
    opener = opener or urllib.request.urlopen
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GameMode-updater"})
        with opener(req, timeout=timeout) as r:
            if not str(r.geturl()).startswith("https://"):
                return None
            raw = r.read(MAX_MANIFEST + 1)
        if len(raw) > MAX_MANIFEST:
            return None
        return validate_manifest(json.loads(raw.decode("utf-8-sig")), repo)
    except (OSError, ValueError):
        return None


def download_installer(manifest, dest, opener=None, progress=None, timeout=30):
    """Baixa o instalador e confere o SHA-256. Retorna dest ou levanta ValueError/OSError."""
    opener = opener or urllib.request.urlopen
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    digest, total = hashlib.sha256(), 0
    req = urllib.request.Request(manifest["url"], headers={"User-Agent": "GameMode-updater"})
    try:
        with opener(req, timeout=timeout) as r, open(part, "wb") as f:
            if not str(r.geturl()).startswith("https://"):
                raise ValueError("o download saiu do https")
            size = int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_INSTALLER:
                    raise ValueError("arquivo grande demais")
                digest.update(chunk)
                f.write(chunk)
                if progress:
                    progress(total, size)
        if digest.hexdigest() != manifest["sha256"]:
            raise ValueError("o arquivo baixado não confere com o publicado (SHA-256)")
        os.replace(part, dest)
        return dest
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise


def update_action(mode, frozen, version, skip, game_running, manual):
    """O que fazer com uma versão nova achada: 'none', 'notify', 'prompt', 'install' ou 'wait'."""
    if manual:
        return "prompt" if frozen else "notify"
    if mode == "off" or version == skip:
        return "none"
    if mode == "notify" or not frozen:
        return "notify"
    if mode == "auto":
        return "wait" if game_running else "install"
    return "prompt"
