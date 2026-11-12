"""
Game Mode com interface gráfica (Windows).

Abra pelo gamemode_gui.pyw (dois cliques). Ele mostra uma caixa com o erro, se algo falhar.
Os três arquivos (gamemode_gui.pyw, gamemode_app.py e gm_mods.py) ficam na mesma pasta.
Não precisa de janela de cmd: se o programa for aberto pelo python.exe, ele se reabre
sozinho sem console. Para ver mensagens de erro num terminal:  python gamemode_app.py --console

Ligue o botão e jogue. Enquanto o jogo estiver aberto, o programa:
  1. Sobe a prioridade de CPU do jogo e tira ele do modo de eficiência.
  2. Deixa apps de segundo plano mais lentos (prioridade baixa, modo de eficiência
     e prioridade de memória baixa: o Windows tira a RAM deles primeiro).
  3. Pede para os apps devolverem memória ociosa e repete isso a cada 60 segundos.
  4. Mostra na tabela quais apps foram diminuídos e quanta memória cada um liberou.
Ao desligar, fechar o jogo ou fechar a janela, tudo volta ao normal.

Não injeta nada no jogo e não fecha nenhum programa. Muda o plano de energia para Alto
desempenho só enquanto o jogo roda (dá para desligar em Opções). Não precisa de administrador
para processos seus; só o QoS pede permissão.
"""

import os
import sys

if __name__ == "__main__" and not (getattr(sys, "frozen", False) or "__compiled__" in globals()):
    # Roda o programa dentro de um try: erro ao carregar vira caixa de aviso + arquivo erro.txt
    # (sem isso, abrindo sem cmd, o programa fechava calado).
    try:
        import runpy
        runpy.run_path(__file__, run_name="gamemode_app_real")["run_main"]()
    except SystemExit:
        raise
    except BaseException:
        import traceback as _tb
        _details = _tb.format_exc()
        try:
            _folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "GameModeLite")
            os.makedirs(_folder, exist_ok=True)
            with open(os.path.join(_folder, "erro.txt"), "a", encoding="utf-8") as _f:
                _f.write(_details + "\n\n")
        except Exception:
            pass
        try:
            import ctypes as _ct
            _ct.windll.user32.MessageBoxW(
                None, tr("O Game Mode não conseguiu abrir:\n\n") + _details[-1400:], "Game Mode", 0x10)
        except Exception:
            pass
    sys.exit(0)

import atexit
import ctypes
import gc
import json
import math
import os
import platform
import queue
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from collections import Counter, defaultdict, deque
from ctypes import wintypes

try:
    import gm_i18n
    from gm_i18n import tr
except Exception:          # without the translator everything still works, in Portuguese
    gm_i18n = None

    def tr(text):
        return text

if sys.platform != "win32":
    sys.exit(tr("Este programa só funciona no Windows."))

import tkinter as tk
from tkinter import messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # abre com dois cliques de qualquer pasta
MODS_ERROR = ""
try:
    import gm_mods
except ModuleNotFoundError as _exc:
    gm_mods = None
    MODS_ERROR = (tr("Não achei o arquivo gm_mods.py ao lado do programa.\n"
                  "Coloque os três arquivos na mesma pasta e abra de novo."))
    if _exc.name != "gm_mods":
        MODS_ERROR = traceback.format_exc()
except Exception:
    gm_mods = None
    MODS_ERROR = traceback.format_exc()

try:
    import gm_extras
except Exception:
    gm_extras = None
    EXTRAS_ERROR = traceback.format_exc()

try:
    import gm_games
except Exception:
    gm_games = None

# --------------------------------------------------------------------------
# Configurações
# --------------------------------------------------------------------------

DEFAULT_GAME = "RobloxPlayerBeta.exe"

DEFAULT_CALM = {
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe",
    "epicgameslauncher.exe", "battle.net.exe", "eadesktop.exe", "origin.exe",
    "galaxyclient.exe", "ubisoftconnect.exe", "upc.exe", "steamwebhelper.exe",
    "onedrive.exe", "dropbox.exe", "googledrivefs.exe", "googleupdate.exe",
    "msedgeupdate.exe", "adobeupdateservice.exe", "ccxprocess.exe",
    "teams.exe", "ms-teams.exe", "slack.exe", "zoom.exe",
}

DEFAULT_PROTECT = {
    "discord.exe", "spotify.exe", "system", "registry", "csrss.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "smss.exe", "wininit.exe", "dwm.exe", "explorer.exe",
    "audiodg.exe", "svchost.exe", "fontdrvhost.exe", "sihost.exe", "ctfmon.exe",
    "obs64.exe",
}

# Quanto o programa olha as coisas: normal, leve ou mínimo (o mais leve). Ajustável em Opções.
PERF_LEVELS = {
    "normal": {"hud": 66, "poll": 0.005, "engine": 1.0, "idle": 1000, "minimized": 2000},
    "light": {"hud": 100, "poll": 0.010, "engine": 1.5, "idle": 1500, "minimized": 3000},
    "minimal": {"hud": 150, "poll": 0.016, "engine": 2.0, "idle": 2000, "minimized": 4000},
}
PERF = dict(PERF_LEVELS["normal"])


def set_perf(level):
    PERF.clear()
    PERF.update(PERF_LEVELS.get(level, PERF_LEVELS["normal"]))


POLL_SECONDS = 2.0           # esperando o jogo abrir
FNF_PRESET_LABELS = [("dfjk", "D F J K"), ("arrows", tr("Setas")), ("wasd", "A S W D"),
                     ("custom", tr("Personalizado"))]
FNF_POS_LABELS = [("bl", tr("Embaixo à esquerda")), ("br", tr("Embaixo à direita")),
                  ("tl", tr("Em cima à esquerda")), ("tr", tr("Em cima à direita"))]
HOTKEY_LABELS = [("none", tr("Nenhuma")), ("f6", "F6"), ("f7", "F7"), ("f8", "F8"), ("f9", "F9"),
                 ("f10", "F10")]
POLL_ACTIVE_SECONDS = 3.0    # jogo aberto (menos trabalho enquanto você joga)
RETRIM_SECONDS = 60.0
POLL_IDLE_SLOW_SECONDS = 5.0  # depois de 1 min esperando o jogo, olha menos vezes
IDLE_SLOW_AFTER = 60.0
APP_VERSION = "2.6 (update notice, performance settings)"
UPDATE_REPO = "RegenKaboom/gamemode"                  # onde as versões novas são publicadas (GitHub Releases)
UPDATE_MANIFEST_URL = f"https://github.com/{UPDATE_REPO}/releases/latest/download/latest.json"
UPDATE_PAGE = f"https://github.com/{UPDATE_REPO}/releases/latest"
UPDATE_MODE_LABELS = [("ask", tr("Avisar e perguntar antes de instalar")),
                      ("auto", tr("Instalar sozinho (só com o jogo fechado)")),
                      ("notify", tr("Só avisar e abrir a página de download")),
                      ("off", tr("Nunca procurar atualização"))]

DEFAULT_SETTINGS = {
    "game": DEFAULT_GAME,
    "high": False,           # prioridade ALTA no jogo (senão: acima do normal)
    "eco": True,             # modo de eficiência nos apps calmos
    "gpu_pref": False,       # Roblox usa a GPU de alto desempenho (preferência do Windows)
    "gpu_paths": [],         # exes que o programa mudou (para poder desfazer)
    "win_tweaks": {"backup": None},   # valores de antes dos ajustes de jogo do Windows
    "mem_priority": True,    # prioridade de memória baixa nos apps calmos
    "io_priority": True,     # disco com prioridade baixa nos apps calmos
    "limit_cpu": False,      # apps calmos presos a poucos núcleos (PCs com mais de 4)
    "power_plan": True,      # plano de energia Alto desempenho enquanto o jogo roda
    "trim": True,            # liberar memória
    "trim_all": True,        # liberar de todos os apps, não só os da lista
    "retrim": True,          # repetir a liberação a cada 60 s
    "unslow_active": True,   # app lento em uso volta ao normal até você sair dele
    "calm": sorted(DEFAULT_CALM),
    "protect": sorted(DEFAULT_PROTECT),
    "autostart_mode": False,   # ligar o Game Mode quando o programa abre
    "start_minimized": False,  # abrir minimizado
    "window": {"w": 0, "h": 0, "x": -1, "y": -1, "tab": "game"},
    "extras": {"break_on": False, "break_min": 60, "ping_alert": 0},   # pausa; aviso de ping (ms, 0 = off)
    "client": (gm_extras.client_defaults() if gm_extras is not None
               else {"style": "dark", "accent": "cyan"}),         # visual estilo Feather/Badlion
    "hotkeys": {"gamemode": "none", "move": "none"},
    "gamebar_backup": "",        # como estava o Xbox Game Bar antes de desligar (JSON)
    "profiles_v": 0,
    "keep_awake": True,      # tela e PC acordados enquanto o jogo roda
    "sounds": True,          # bipe ao ligar/desligar o Game Mode
    "perf": {"level": "normal"},   # uso de processador do próprio programa: normal | light | minimal
    "fso_paths": [],         # exes que o programa mudou nas otimizações de tela cheia (para poder desfazer)
    "seen_version": "",      # última versão que abriu aqui (para avisar depois de atualizar)
    "update_notice": True,   # avisar quando o Game Mode for atualizado
    "ui": {"lang": "", "theme": ""},    # "" = not chosen yet; then auto | en | pt | es / auto | dark | light
    "updates": {"mode": "ask", "skip": "", "last_check": 0.0},
    "fnf": {"preset": "dfjk", "keys": ["d", "f", "j", "k"], "pos": "bl", "auto_reset": False,
            "hotkey_toggle": "none", "hotkey_reset": "none"},
    "auto_game": False,          # trocar sozinho para o jogo da lista que abrir
    "profiles": [                # um perfil por jogo
        {"exe": "RobloxPlayerBeta.exe", "name": "Roblox", "ping_host": "roblox.com",
         "gpu": False, "look": "Classic", "path": ""},
        {"exe": "Funkin.exe", "name": "Friday Night Funkin'", "ping_host": "",
         "gpu": False, "look": "FNF", "path": ""},
        {"exe": "javaw.exe", "name": "Minecraft Java", "ping_host": "hypixel.net",
         "gpu": False, "look": "Client", "path": ""},
        {"exe": "Minecraft.Windows.exe", "name": "Minecraft Bedrock", "ping_host": "xbox.com",
         "gpu": False, "look": "Client", "path": ""},
    ],
    "mods": {
        "qos": {"preset": "high", "dscp": 46, "all_networks": True, "nla_new": False},
        "move": {"mode": "last", "fwd": "w", "back": "s", "left": "a", "right": "d",
                 "only_game": True},
    },
    "overlay": {
        "on": False,             # overlays ligados
        "only_game": True,       # só enquanto o jogo está na frente
        "look": "Classic",       # Classic | Minimal | Neon | Competitive
        "scale": 100,            # tamanho, em %
        "opacity": 90,           # opacidade, em %
        "ping_host": "roblox.com",
        "show": {"stats": True, "keys": True, "mouse": True, "cps": False, "crosshair": False, "fnf": False,
                 "client": False},
    },
    "crosshair": {
        "shape": "cross",        # cross | tcross | dot | circle
        "color": "green",
        "size": 14,
        "gap": 4,
        "thick": 2,
    },
    "shader": {
        "on": False,             # shader ligado
        "only_game": False,      # só enquanto o jogo está na frente
        "preset": "",
        "brightness": 0,         # -100 a 100
        "contrast": 0,           # -100 a 100
        "saturation": 100,       # 0 a 200 (0 = preto e branco)
        "warmth": 0,             # -100 (frio) a 100 (quente)
        "tint": 0,               # -100 (verde) a 100 (magenta)
        "amount": 100,           # força do shader, 0 a 100
    },
    "display": {
        "level": 100,          # brilho de tela em % (100 = normal)
        "game_boost": False,   # mais claro enquanto o jogo está em primeiro plano
        "boost": 130,          # brilho usado dentro do jogo
        "hotkey": "none",      # tecla que liga/desliga o brilho do jogo
        "flash_sens": 60,      # sensibilidade ao flash (0 a 100)
        "flash_amount": 30,    # quanto a tela escurece num flash (pontos de %)
        "flash_release": 40,   # velocidade para voltar ao brilho normal (1 a 100)
        "measure": "mix",      # medir por: mix | shadow | mean
        "center": 2,           # peso do centro da imagem (1 a 3)
        "area": "window",      # window | screen
        "step": 2,             # mudança mínima (%) para mexer no brilho
        "method": "auto",      # como ESCURECER: auto | gamma | mag | overlay
        "method_up": "auto",   # como CLAREAR: auto | gamma | mag | overlay
        "on": {                # interruptores: desligado = a função não age até ligar de novo
            "flash": True,     # escurecer rápido em flashes
            "center": True,    # dar mais peso ao centro da tela
            "step": True,      # ignorar mudanças pequenas
            "hotkey": True,    # usar a tecla de atalho
            "comp": False,     # descontar da medição o brilho que o programa já aplicou
            "only_game": False,  # clarear só enquanto o jogo está na frente (fora dele: normal)
        },
    },
}

SETTINGS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "GameModeLite", "settings.json")
PLAYTIME_PATH = os.path.join(os.path.dirname(SETTINGS_PATH), "playtime.json")


def _merge_settings(default, saved):
    """Pega do arquivo só o que existe nos padrões e tem o mesmo tipo (aceita int no lugar de float)."""
    for key, value in default.items():
        if key not in saved:
            continue
        other = saved[key]
        if isinstance(value, dict):
            if isinstance(other, dict):
                _merge_settings(value, other)
        elif type(other) is type(value) or (isinstance(value, float) and type(other) is int):
            default[key] = float(other) if isinstance(value, float) else other
    return default


_FIRST_RUN = not os.path.isfile(SETTINGS_PATH)   # primeira vez neste PC: não avisa de atualização


def load_settings():
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            _merge_settings(settings, saved)
    except (OSError, ValueError):
        pass
    return settings


def write_error_log(text):
    try:
        folder = os.path.dirname(SETTINGS_PATH)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "erro.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + text + "\n\n")
    except OSError:
        pass


def save_settings(settings):
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Windows API
# --------------------------------------------------------------------------

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

PROCESS_SET_QUOTA = 0x0100
PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ACCESS = PROCESS_SET_QUOTA | PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION

BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
HIGH_PRIORITY_CLASS = 0x00000080

ProcessMemoryPriority = 0
ProcessPowerThrottling = 4
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
MEMORY_PRIORITY_VERY_LOW = 1
MEMORY_PRIORITY_NORMAL = 5

ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("ControlMask", wintypes.ULONG),
        ("StateMask", wintypes.ULONG),
    ]


class MEMORY_PRIORITY_INFORMATION(ctypes.Structure):
    _fields_ = [("MemoryPriority", wintypes.ULONG)]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetPriorityClass.argtypes = [wintypes.HANDLE]
kernel32.GetPriorityClass.restype = wintypes.DWORD
kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.SetPriorityClass.restype = wintypes.BOOL
kernel32.SetProcessInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel32.SetProcessInformation.restype = wintypes.BOOL
kernel32.K32EmptyWorkingSet.argtypes = [wintypes.HANDLE]
kernel32.K32EmptyWorkingSet.restype = wintypes.BOOL
kernel32.K32GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetTickCount64.argtypes = []
kernel32.GetTickCount64.restype = ctypes.c_ulonglong


def list_processes():
    """Retorna {pid: nome_em_minúsculas} dos processos atuais."""
    procs = {}
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return procs
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            procs[entry.th32ProcessID] = entry.szExeFile.lower()
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return procs



try:
    # --- desempenho extra: disco e núcleos ----------------------------------------------------
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtSetInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p,
                                              ctypes.c_ulong]
    ntdll.NtSetInformationProcess.restype = ctypes.c_long
    ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p,
                                                ctypes.c_ulong, ctypes.c_void_p]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    kernel32.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                                ctypes.POINTER(ctypes.c_size_t)]
    kernel32.GetProcessAffinityMask.restype = wintypes.BOOL
    kernel32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    kernel32.SetProcessAffinityMask.restype = wintypes.BOOL
    PROCESS_IO_PRIORITY = 33
    IO_VERY_LOW = 0


    def get_io_priority(h):
        value = ctypes.c_ulong(0)
        if ntdll.NtQueryInformationProcess(h, PROCESS_IO_PRIORITY, ctypes.byref(value), 4, None) >= 0:
            return value.value
        return None


    def set_io_priority(h, level):
        value = ctypes.c_ulong(level)
        return ntdll.NtSetInformationProcess(h, PROCESS_IO_PRIORITY, ctypes.byref(value), 4) >= 0


    def limit_affinity(h):
        """Prende o processo aos últimos núcleos (deixa os primeiros livres para o jogo).
        Retorna a máscara original para restaurar, ou 0 se não mexeu."""
        proc, system = ctypes.c_size_t(0), ctypes.c_size_t(0)
        if not kernel32.GetProcessAffinityMask(h, ctypes.byref(proc), ctypes.byref(system)):
            return 0
        bits = [i for i in range(64) if (system.value >> i) & 1]
        if len(bits) <= 4:
            return 0
        keep = bits[-max(2, len(bits) // 4):]
        mask = sum(1 << b for b in keep) & proc.value
        if not mask or mask == proc.value:
            return 0
        return proc.value if kernel32.SetProcessAffinityMask(h, mask) else 0
except Exception as _exc:  # DLL/função ausente: desliga só este recurso
    write_error_log(tr("Disco/núcleos indisponíveis: ") + repr(_exc))
    IO_VERY_LOW = 0

    def get_io_priority(h):
        return None

    def set_io_priority(h, level):
        return False

    def limit_affinity(h):
        return 0


def open_process(pid):
    """Retorna (handle, erro). handle é None se falhou."""
    h = kernel32.OpenProcess(PROCESS_ACCESS, False, pid)
    if not h:
        return None, ctypes.get_last_error()
    return h, 0


def get_priority(h):
    return kernel32.GetPriorityClass(h) or None


def set_priority(h, priority_class):
    if kernel32.SetPriorityClass(h, priority_class):
        return True, 0
    return False, ctypes.get_last_error()


def set_eco(h, mode):
    """mode: 'on' = modo eficiência, 'off' = nunca limitar, 'default' = o Windows decide."""
    control, state = {"on": (1, 1), "off": (1, 0), "default": (0, 0)}[mode]
    info = PROCESS_POWER_THROTTLING_STATE(
        PROCESS_POWER_THROTTLING_CURRENT_VERSION,
        PROCESS_POWER_THROTTLING_EXECUTION_SPEED * control,
        PROCESS_POWER_THROTTLING_EXECUTION_SPEED * state,
    )
    if kernel32.SetProcessInformation(
            h, ProcessPowerThrottling, ctypes.byref(info), ctypes.sizeof(info)):
        return True, 0
    return False, ctypes.get_last_error()


def set_memprio(h, value):
    """Prioridade de memória (1 = muito baixa ... 5 = normal)."""
    info = MEMORY_PRIORITY_INFORMATION(value)
    if kernel32.SetProcessInformation(
            h, ProcessMemoryPriority, ctypes.byref(info), ctypes.sizeof(info)):
        return True, 0
    return False, ctypes.get_last_error()


def working_set(h):
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    if kernel32.K32GetProcessMemoryInfo(h, ctypes.byref(counters), counters.cb):
        return counters.WorkingSetSize
    return 0


def trim_memory(h):
    """Retorna (bytes_liberados, ok, erro)."""
    before = working_set(h)
    if not kernel32.K32EmptyWorkingSet(h):
        return 0, False, ctypes.get_last_error()
    after = working_set(h)
    return max(0, before - after), True, 0


def tune_self(low_power):
    """Parado: prioridade baixa + modo de eficiência (quase não gasta CPU).
    Com Movement Helper/HitFix ligados: prioridade alta e sem eficiência, para responder na hora."""
    h = kernel32.GetCurrentProcess()
    if low_power:
        set_priority(h, BELOW_NORMAL_PRIORITY_CLASS)
        set_eco(h, "on")
    else:
        set_priority(h, ABOVE_NORMAL_PRIORITY_CLASS)
        set_eco(h, "off")


def whats_new_text():
    """The 'what is new' text for this version, in the language chosen (from NOVIDADES.txt next to the program)."""
    lang = gm_i18n.lang() if gm_i18n is not None else "pt"
    for base in (os.path.dirname(os.path.abspath(sys.argv[0])), os.path.dirname(os.path.abspath(__file__))):
        try:
            with open(os.path.join(base, "NOVIDADES.txt"), encoding="utf-8-sig") as f:
                return gm_extras.notes_for(f.read(), lang) if gm_extras is not None else ""
        except OSError:
            continue
    return ""


def trim_self():
    """Devolve ao Windows a memória ociosa do próprio programa."""
    kernel32.K32EmptyWorkingSet(kernel32.GetCurrentProcess())


# --------------------------------------------------------------------------
# Brilho (curva de gama da tela, como o Lyre: "software brightness")
# --------------------------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
gdi32.SetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.c_void_p]
gdi32.SetDeviceGammaRamp.restype = wintypes.BOOL
gdi32.GetDeviceGammaRamp.argtypes = [wintypes.HDC, ctypes.c_void_p]
gdi32.GetDeviceGammaRamp.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
BRIGHT_MIN, BRIGHT_MAX = 50, 200
GammaRamp = (ctypes.c_ushort * 256) * 3
_original_ramp = None
_ramp_changed = False


def make_ramp(percent):
    """Curva de gama: 100 = normal, acima de 100 clareia as sombras sem estourar o branco."""
    gamma = max(0.1, percent / 100.0)
    ramp = GammaRamp()
    for i in range(256):
        value = int(round(65535 * ((i / 255.0) ** (1.0 / gamma))))
        value = max(0, min(65535, value))
        for channel in range(3):
            ramp[channel][i] = value
    return ramp


def _gamma_call(fn, ramp):
    hdc = user32.GetDC(None)
    if not hdc:
        return False
    try:
        return bool(fn(hdc, ctypes.byref(ramp)))
    finally:
        user32.ReleaseDC(None, hdc)


# --- Filtro de cor do Windows (Magnification): alternativa quando a curva da tela falha ---
try:
    magnification = ctypes.WinDLL("Magnification")

    class MAGCOLOREFFECT(ctypes.Structure):
        _fields_ = [("transform", ctypes.c_float * 25)]

    magnification.MagInitialize.argtypes = []
    magnification.MagInitialize.restype = wintypes.BOOL
    magnification.MagUninitialize.argtypes = []
    magnification.MagUninitialize.restype = wintypes.BOOL
    magnification.MagSetFullscreenColorEffect.argtypes = [ctypes.POINTER(MAGCOLOREFFECT)]
    magnification.MagSetFullscreenColorEffect.restype = wintypes.BOOL
    HAS_MAG = True
except Exception as _exc:  # sem Magnification.dll: só a curva da tela fica disponível
    write_error_log(tr("Filtro de cor indisponível: ") + repr(_exc))
    HAS_MAG = False

_mag_on = False


def _mag_params(percent):
    """(escala, deslocamento) do filtro. Acima de 100 também levanta as sombras, que é o que
    ajuda a enxergar em cena escura (só multiplicar quase não mexe no escuro)."""
    if percent >= 100:
        t = (percent - 100) / 100.0
        return 1.0 + 0.5 * t, 0.08 * t
    return percent / 100.0, 0.0


_mag_percent = 100   # brilho pedido pelo método "filtro de cor" (100 = nada)
_grade = None        # shader ligado (matriz 5x5) ou None


def _identity5():
    return [1.0 if i == j else 0.0 for i in range(5) for j in range(5)]


def _matmul5(a, b):
    return [sum(a[i * 5 + k] * b[k * 5 + j] for k in range(5))
            for i in range(5) for j in range(5)]


def _brightness_matrix(percent):
    scale, offset = _mag_params(percent)
    return [scale, 0, 0, 0, 0,
            0, scale, 0, 0, 0,
            0, 0, scale, 0, 0,
            0, 0, 0, 1, 0,
            offset, offset, offset, 0, 1]


def _send_matrix(values):
    effect = MAGCOLOREFFECT()
    for i, v in enumerate(values):
        effect.transform[i] = v
    return bool(magnification.MagSetFullscreenColorEffect(ctypes.byref(effect)))


def _mag_commit():
    """Junta shader + brilho num filtro só (o Windows aceita um filtro por vez)."""
    global _mag_on
    if not HAS_MAG:
        return False
    m = _identity5()
    if _grade:
        m = _matmul5(m, _grade)
    if _mag_percent != 100:
        m = _matmul5(m, _brightness_matrix(_mag_percent))
    if all(abs(x - y) < 1e-6 for x, y in zip(m, _identity5())):
        if not _mag_on:
            return True
        ok = _send_matrix(m)
        magnification.MagUninitialize()
        _mag_on = False
        return ok
    if not _mag_on:
        if not magnification.MagInitialize():
            return False
        _mag_on = True
    return _send_matrix(m)


def mag_set(percent):
    """Brilho por filtro de cor. True se o Windows aceitou."""
    global _mag_percent
    previous = _mag_percent
    _mag_percent = percent
    if _mag_commit():
        return True
    _mag_percent = previous
    return False


def mag_restore():
    global _mag_percent
    _mag_percent = 100
    return _mag_commit()


def shader_apply(matrix):
    """Liga um shader (matriz 5x5). O brilho por filtro continua valendo junto."""
    global _grade
    previous = _grade
    _grade = matrix
    if _mag_commit():
        return True
    _grade = previous
    return False


def shader_clear():
    global _grade
    _grade = None
    return _mag_commit()


# --- Shaders (visual do jogo), no estilo do Lyre: presets + contraste, saturação, calor... ---
SHADER_DEFAULT = {"brightness": 0, "contrast": 0, "saturation": 100, "warmth": 0, "tint": 0,
                  "amount": 100}
SHADER_PRESETS = {   # nome: (descrição, brilho, contraste, saturação, calor, matiz)
    "Vivid": (tr("Cores mais ricas, um pouco mais de punch."), 0, 15, 135, 8, 0),
    "Clarity": (tr("Nítido e claro para achar jogadores."), 8, 22, 110, 0, 0),
    "Cinematic": (tr("Contraste profundo, quente e dramático."), -5, 30, 95, 15, 5),
    "Sunset": (tr("Hora dourada o dia todo."), 3, 10, 115, 45, 5),
    "Arctic": (tr("Azuis frios e limpos."), 3, 8, 95, -45, 0),
    "Retro": (tr("Filme desbotado com realces quentes."), 5, -15, 80, 25, 5),
    "Noir": (tr("Preto e branco com sombras duras."), 0, 40, 0, 0, 0),
    "Dream": (tr("Brilho suave, pastel."), 10, -20, 90, 10, 15),
}


def grade_matrix(g):
    """Shader -> matriz 5x5 do filtro de cor (ordem: saturação, contraste, calor/matiz, brilho)."""
    sat = max(0.0, g["saturation"] / 100.0)
    contrast = 1.0 + g["contrast"] / 100.0
    warm, tint = g["warmth"] / 100.0, g["tint"] / 100.0
    lum = (0.2126, 0.7152, 0.0722)

    def eye():
        return [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    def diag(r, g_, b):
        return [[r, 0.0, 0.0], [0.0, g_, 0.0], [0.0, 0.0, b]]

    steps = [
        ([[(1.0 - sat) * lum[i] + (sat if i == j else 0.0) for i in range(3)]
          for j in range(3)], [0.0, 0.0, 0.0]),
        (diag(contrast, contrast, contrast), [0.5 * (1.0 - contrast)] * 3),
        (diag(1.0 + 0.20 * warm + 0.05 * tint, 1.0 - 0.15 * tint, 1.0 - 0.20 * warm + 0.05 * tint),
         [0.0, 0.0, 0.0]),
        (eye(), [g["brightness"] / 100.0 * 0.25] * 3),
    ]
    t, o = eye(), [0.0, 0.0, 0.0]
    for step_t, step_o in steps:
        o = [sum(step_t[i][k] * o[k] for k in range(3)) + step_o[i] for i in range(3)]
        t = mul(step_t, t)
    a = max(0.0, min(1.0, g["amount"] / 100.0))
    t = [[a * t[i][j] + (1.0 - a) * (1.0 if i == j else 0.0) for j in range(3)] for i in range(3)]
    o = [a * v for v in o]
    m = _identity5()
    for i in range(3):
        for j in range(3):
            m[i * 5 + j] = t[j][i]
    for j in range(3):
        m[20 + j] = o[j]
    return m


def _gamma_restore():
    """Devolve a curva original da tela. True se deu certo (ou se nada tinha mudado)."""
    global _ramp_changed
    if not _ramp_changed:
        return True
    ramp = _original_ramp if _original_ramp is not None else make_ramp(100)
    ok = _gamma_call(gdi32.SetDeviceGammaRamp, ramp)
    if ok:
        _ramp_changed = False
    return ok


def _gamma_try(value, verify=True):
    """Aplica a curva e (se verify) confere se o driver guardou de verdade."""
    global _ramp_changed
    want = make_ramp(value)
    if not _gamma_call(gdi32.SetDeviceGammaRamp, want):
        return False
    _ramp_changed = True
    check = GammaRamp()
    if verify and _gamma_call(gdi32.GetDeviceGammaRamp, check):
        for i in (32, 96, 160, 224):
            if abs(check[1][i] - want[1][i]) > 1024:
                _gamma_restore()
                return False
    return True


def restore_brightness():
    """Tira qualquer brilho aplicado (curva e filtro). True se deu certo."""
    ok_gamma = _gamma_restore()
    ok_mag = mag_restore()
    return ok_gamma and ok_mag


BRIGHT_METHOD_LABELS = [("auto", tr("Automático")), ("gamma", tr("Curva da tela (gama)")),
                        ("mag", tr("Filtro de cor do Windows")),
                        ("overlay", tr("Camada sobre a tela"))]


def set_brightness(percent, method="auto"):
    """Aplica o brilho. Retorna (valor aplicado, método usado) ou (None, '') se nada funcionou.
    'gamma' = curva da tela; 'mag' = filtro de cor. 'auto' escolhe pela direção: para escurecer
    tenta a curva e depois o filtro; para clarear tenta o filtro primeiro (a curva costuma ser
    aceita e ignorada pelo driver quando clareia)."""
    global _original_ramp
    if _original_ramp is None:
        ramp = GammaRamp()
        if _gamma_call(gdi32.GetDeviceGammaRamp, ramp):
            _original_ramp = ramp
    value = int(max(BRIGHT_MIN, min(BRIGHT_MAX, percent)))
    if value == 100:
        return (100, "normal") if restore_brightness() else (None, "")
    if method == "auto":
        order = ("mag", "gamma") if value > 100 else ("gamma", "mag")
    else:
        order = (method,)
    best = None
    for how in order:
        if how == "gamma":
            step = -5 if value > 100 else 5
            v, got = value, None
            while v != 100:
                if _gamma_try(v, method == "auto"):
                    got = v
                    break
                v += step
                if (step < 0 and v < 100) or (step > 0 and v > 100):
                    v = 100
            if got == value:
                mag_restore()
                return value, "gamma"
            if got:
                best = got
        elif how == "mag" and mag_set(value):
            _gamma_restore()
            return value, "mag"
    if method == "gamma":
        return (best, "gamma") if best else (None, "gamma")
    if best:
        return best, "gamma"
    return None, ""


# --- Camada sobre a tela: não depende de driver. Branca clareia, preta escurece. ---------
try:
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    _GetLong = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    _SetLong = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    _GetLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _GetLong.restype = ctypes.c_ssize_t
    _SetLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _SetLong.restype = ctypes.c_ssize_t
except Exception as _exc:
    write_error_log(tr("Camada sobre a tela sem API: ") + repr(_exc))


class DimOverlay:
    """Janela transparente por cima de tudo (o mouse passa direto por ela)."""

    def __init__(self, root):
        self.root = root
        self.win = None
        self.visible = False

    def _area(self):
        x, y = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        w, h = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        if w <= 0 or h <= 0:
            x, y, w, h = 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        return x, y, w, h

    def _create(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg="#000000")
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.01)
        x, y, w, h = self._area()
        win.geometry(f"{w}x{h}{x:+d}{y:+d}")
        win.update_idletasks()
        hwnd = user32.GetAncestor(win.winfo_id(), 2) or win.winfo_id()
        style = _GetLong(hwnd, -20)
        # camada + clique passa direto + não rouba foco + fora da barra de tarefas
        _SetLong(hwnd, -20, style | 0x00080000 | 0x00000020 | 0x08000000 | 0x00000080)
        self.win = win

    def set(self, percent):
        """percent > 100 clareia (véu branco), < 100 escurece (véu preto). True se deu certo."""
        if percent == 100:
            self.hide()
            return True
        try:
            if self.win is None:
                self._create()
            if percent > 100:
                color, alpha = "#ffffff", min(0.55, (percent - 100) / 100.0 * 0.5)
            else:
                color, alpha = "#000000", min(0.9, (100 - percent) / 100.0)
            self.win.configure(bg=color)
            self.win.attributes("-alpha", max(0.01, alpha))
            x, y, w, h = self._area()
            self.win.geometry(f"{w}x{h}{x:+d}{y:+d}")
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.win.lift()
            self.visible = True
            return True
        except Exception as exc:
            write_error_log(tr("Camada sobre a tela falhou: ") + repr(exc))
            self.win = None
            self.visible = False
            return False

    def keep_on_top(self):
        if self.visible and self.win is not None:
            try:
                self.win.attributes("-topmost", True)
                self.win.lift()
            except Exception:
                pass

    def hide(self):
        self.visible = False
        if self.win is not None:
            try:
                self.win.withdraw()
            except Exception:
                self.win = None


# --------------------------------------------------------------------------
# Overlays (HUD): CPU/RAM/ping, teclas, CPS e mira
# --------------------------------------------------------------------------

try:
    class _FILETIME(ctypes.Structure):
        _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]

    class _MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32),
                    ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64)]

    kernel32.GetSystemTimes.argtypes = [ctypes.POINTER(_FILETIME)] * 3
    kernel32.GetSystemTimes.restype = wintypes.BOOL
    kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MEMORYSTATUSEX)]
    kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL
    HAS_STATS_API = True
except Exception as _exc:
    write_error_log(tr("Leitura de CPU/RAM indisponível: ") + repr(_exc))
    HAS_STATS_API = False

HUD_COLORS = {"green": "#00ff66", "red": "#ff3b3b", "white": "#ffffff", "cyan": "#22d3ee",
              "yellow": "#facc15"}
CROSS_COLOR_LABELS = [("green", tr("Verde")), ("red", tr("Vermelho")), ("white", tr("Branco")),
                      ("cyan", tr("Ciano")), ("yellow", tr("Amarelo"))]
CROSS_SHAPE_LABELS = [("cross", tr("Cruz")), ("tcross", tr("Cruz em T")), ("dot", tr("Ponto")),
                      ("circle", tr("Círculo"))]
WATCH_KEYS = {"W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44, "SHIFT": 0x10, "SPACE": 0x20,
              "LMB": 0x01, "RMB": 0x02, "CTRL": 0x11}
HUD_LOOKS = {   # nome: (descrição, elementos que ele liga)
    "Classic": (tr("Números em cima à esquerda, teclas e mouse embaixo à esquerda."),
                {"stats": True, "keys": True, "mouse": True, "cps": False}),
    "Minimal": (tr("Só os números, em cima à direita, sem caixas."),
                {"stats": True, "keys": False, "mouse": False, "cps": False}),
    "Neon": (tr("Teclas neon grandes, embaixo no centro."),
             {"stats": False, "keys": True, "mouse": False, "cps": False}),
    "Competitive": (tr("Gráfico de CPS esquerdo/direito, ping colorido e linha do mouse."),
                    {"stats": True, "keys": False, "mouse": True, "cps": True}),
}

CLIENT_STYLE_LABELS = [("dark", tr("Caixa escura")), ("text", tr("Só texto com sombra"))]
if gm_extras is not None:
    for _look in HUD_LOOKS.values():
        _look[1].setdefault("fnf", False)
        _look[1].setdefault("client", False)
    HUD_LOOKS["FNF"] = (tr("4 setas que acendem quando você aperta, com KPS (apertos por segundo) e "
                        "contagem. Feito para Friday Night Funkin'."),
                        {"stats": False, "keys": False, "mouse": False, "cps": False, "fnf": True,
                         "client": False})
    HUD_LOOKS["Client"] = (tr("Estilo Feather e Badlion: caixinhas com CPS, ping, CPU, RAM, RAM do jogo, "
                           "relógio e tempo de sessão, mais as teclas. Dá para ligar e mover cada uma."),
                           {"stats": False, "keys": False, "mouse": False, "cps": False, "fnf": False,
                            "client": True})


def ping_color(ms):
    if ms is None:
        return "#9ca3af"
    return "#4ade80" if ms <= 60 else "#facc15" if ms <= 120 else "#f87171"


class StatsReader:
    """CPU e RAM do PC, e ping (tempo de conexão TCP até um servidor)."""

    def __init__(self):
        self.cpu = 0.0
        self.ram = 0.0
        self.ping = None
        self._prev = None
        self._host = ""
        self._addr = None
        self._active = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    def poll(self):
        """CPU e RAM (chamar ~1 vez por segundo)."""
        if not HAS_STATS_API:
            return
        idle, kern, user = _FILETIME(), _FILETIME(), _FILETIME()
        if kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
            def total(f):
                return (f.hi << 32) | f.lo
            now = (total(idle), total(kern), total(user))
            if self._prev:
                busy = (now[1] - self._prev[1]) + (now[2] - self._prev[2])
                if busy > 0:
                    self.cpu = max(0.0, min(100.0, (busy - (now[0] - self._prev[0])) * 100.0 / busy))
            self._prev = now
        mem = _MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
            self.ram = float(mem.dwMemoryLoad)

    def set_host(self, host):
        self._host = host.strip()
        self._addr = None
        self.ping = None

    def set_active(self, on):
        if on:
            self._active.set()
            if self._thread is None:
                self._thread = threading.Thread(target=self._ping_loop, daemon=True)
                self._thread.start()
        else:
            self._active.clear()

    def _ping_once(self):
        host = self._host
        if not host:
            return None
        try:
            if self._addr is None:
                self._addr = socket.gethostbyname(host)
            started = time.perf_counter()
            with socket.create_connection((self._addr, 443), timeout=1.5):
                pass
            return (time.perf_counter() - started) * 1000.0
        except OSError:
            self._addr = None
            return None

    def _ping_loop(self):
        while not self._stop.is_set():
            if self._active.is_set():
                self.ping = self._ping_once()
                self._stop.wait(2.0)
            else:
                self._stop.wait(0.5)

    def stop(self):
        self._stop.set()


class InputWatcher:
    """Teclas e cliques (só lê o estado; não grava o que você digita). Conta CPS."""

    def __init__(self, getter=None):
        self.getter = getter or (lambda vk: user32.GetAsyncKeyState(vk))
        self.down = {name: False for name in WATCH_KEYS}
        self.clicks = {"LMB": deque(), "RMB": deque()}
        self.hist = {"LMB": deque([0.0] * 40, maxlen=40), "RMB": deque([0.0] * 40, maxlen=40)}
        self._last_hist = 0.0
        self.lane_vks = []                  # 4 teclas do FNF (vazio = desligado)
        self.lane_labels = []
        self.lanes = gm_extras.LaneCounter() if gm_extras is not None else None
        self._active = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    def poll_once(self, now):
        for name, vk in WATCH_KEYS.items():
            pressed = bool(self.getter(vk) & 0x8000)
            if pressed and not self.down[name] and name in self.clicks:
                self.clicks[name].append(now)
            self.down[name] = pressed
        if self.lanes is not None and self.lane_vks:
            self.lanes.update(now, [bool(self.getter(vk) & 0x8000) for vk in self.lane_vks])
        for button in self.clicks:
            q = self.clicks[button]
            while q and now - q[0] > 1.0:
                q.popleft()
        if now - self._last_hist >= 0.25:
            self._last_hist = now
            for button in self.clicks:
                self.hist[button].append(float(len(self.clicks[button])))

    def cps(self, button):
        return len(self.clicks[button])

    def set_active(self, on):
        if on:
            self._active.set()
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
        else:
            self._active.clear()

    def _loop(self):
        while not self._stop.is_set():
            if self._active.is_set():
                try:
                    self.poll_once(time.monotonic())
                except Exception:
                    pass
                self._stop.wait(PERF["poll"])
            else:
                self._stop.wait(0.2)

    def stop(self):
        self._stop.set()


def _make_click_through(win):
    """Janela por cima de tudo que o mouse atravessa e que não pega foco."""
    hwnd = user32.GetAncestor(win.winfo_id(), 2) or win.winfo_id()
    style = _GetLong(hwnd, -20)
    _SetLong(hwnd, -20, style | 0x00080000 | 0x00000020 | 0x08000000 | 0x00000080)


HUD_KEY = "#010203"   # cor que vira transparente


class HudOverlay:
    """Desenha os overlays numa janela transparente sobre a tela."""

    def __init__(self, root, settings, stats, inputs):
        self.root = root
        self.settings = settings
        self.stats = stats
        self.inputs = inputs
        self.win = None
        self.canvas = None
        self.visible = False
        self._alpha = None
        self.session_fn = None          # devolve os segundos da sessão (o App liga isso)
        self._mem_at = 0.0
        self._mem_mb = 0.0

    def _screen(self):
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    def _create(self):
        sw, sh = self._screen()
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=HUD_KEY)
        win.attributes("-topmost", True)
        win.attributes("-transparentcolor", HUD_KEY)
        win.geometry(f"{sw}x{sh}+0+0")
        self.canvas = tk.Canvas(win, bg=HUD_KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        win.update_idletasks()
        _make_click_through(win)
        self.win = win

    def set_visible(self, on):
        try:
            if on:
                if self.win is None:
                    self._create()
                alpha = max(0.3, min(1.0, self.settings["overlay"]["opacity"] / 100.0))
                if alpha != self._alpha:
                    self.win.attributes("-alpha", alpha)
                    self._alpha = alpha
                if not self.visible:
                    self.win.deiconify()
                    self.win.attributes("-topmost", True)
                self.visible = True
            elif self.visible and self.win is not None:
                self.win.withdraw()
                self.visible = False
        except Exception as exc:
            write_error_log(tr("Overlay falhou: ") + repr(exc))
            self.win = None
            self.visible = False

    # ---- desenho ----
    def _text(self, x, y, text, size=11, color="#ffffff", anchor="nw", bold=False):
        k = self.settings["overlay"]["scale"] / 100.0
        self.canvas.create_text(x, y, text=text, fill=color, anchor=anchor,
                                font=("Consolas", max(6, int(size * k)), "bold" if bold else "normal"))

    def _box(self, x0, y0, x1, y1, fill="#111827", outline="#374151", width=1):
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=width)

    def _draw_stats(self, x, y, anchor, boxed):
        k = self.settings["overlay"]["scale"] / 100.0
        st = self.stats
        ping = "--" if st.ping is None else f"{st.ping:.0f} ms"
        if boxed:
            w, h = 136 * k, 70 * k
            self._box(x, y, x + w, y + h)
            self._text(x + 10 * k, y + 8 * k, f"CPU  {st.cpu:3.0f}%")
            self._text(x + 10 * k, y + 28 * k, f"RAM  {st.ram:3.0f}%")
            self._text(x + 10 * k, y + 48 * k, tr('PING {}').format(ping), color=ping_color(st.ping), bold=True)
        else:
            char = max(6, int(11 * k)) * 0.62          # largura aproximada de cada letra
            self._text(x, y, ping, color=ping_color(st.ping), anchor="ne", bold=True)
            self._text(x - len(ping) * char - 8 * k, y, f"CPU {st.cpu:.0f}%  ·  RAM {st.ram:.0f}%  ·",
                       anchor="ne", bold=True)

    def _draw_keys(self, x, y, size, pressed_fill, neon):
        k = self.settings["overlay"]["scale"] / 100.0
        s_, gap = size * k, 4 * k
        down = self.inputs.down

        def key(label, kx, ky, w=None):
            on = down.get(label, False)
            w = w or s_
            self._box(kx, ky, kx + w, ky + s_, fill=pressed_fill if on else "#111827",
                      outline=pressed_fill if neon else "#374151", width=2 if neon else 1)
            text = {"SPACE": "SPACE", "SHIFT": "SH"}.get(label, label)
            self._text(kx + w / 2, ky + s_ / 2, text, size=int(size * 0.4),
                       color="#0b1220" if (on and neon) else "#ffffff", anchor="center", bold=True)

        key("W", x + s_ + gap, y)
        key("A", x, y + s_ + gap)
        key("S", x + s_ + gap, y + s_ + gap)
        key("D", x + 2 * (s_ + gap), y + s_ + gap)
        key("SPACE", x, y + 2 * (s_ + gap), 3 * s_ + 2 * gap)

    def _draw_mouse(self, x, y):
        k = self.settings["overlay"]["scale"] / 100.0
        for i, (name, label) in enumerate((("LMB", "L"), ("RMB", "R"))):
            on = self.inputs.down[name]
            x0 = x + i * 84 * k
            self._box(x0, y, x0 + 78 * k, y + 30 * k, fill="#4f8cff" if on else "#111827")
            self._text(x0 + 39 * k, y + 15 * k, f"{label}  {self.inputs.cps(name)} CPS",
                       size=10, anchor="center", bold=True)

    def _draw_cps(self, x, y):
        k = self.settings["overlay"]["scale"] / 100.0
        w, h = 200 * k, 60 * k
        self._box(x, y, x + w, y + h)
        top = max(10.0, max(max(self.inputs.hist["LMB"]), max(self.inputs.hist["RMB"])))
        for name, color in (("LMB", "#4f8cff"), ("RMB", "#f472b6")):
            values = list(self.inputs.hist[name])
            step = w / max(1, len(values) - 1)
            points = []
            for i, v in enumerate(values):
                points += [x + i * step, y + h - 4 * k - (h - 8 * k) * min(1.0, v / top)]
            self.canvas.create_line(*points, fill=color, width=2)
        self._text(x, y + h + 4 * k, tr('L {}  R {} CPS').format(self.inputs.cps('LMB'), self.inputs.cps('RMB')),
                   size=10, bold=True)

    def _draw_fnf(self, sw, sh):
        lanes = getattr(self.inputs, "lanes", None)
        labels = getattr(self.inputs, "lane_labels", [])
        if lanes is None or len(labels) != 4:
            return
        k = self.settings["overlay"]["scale"] / 100.0
        cell, gap, pad = 56 * k, 8 * k, 10 * k
        w, h = 4 * cell + 3 * gap, cell + 50 * k
        pos = self.settings["fnf"]["pos"]
        x0 = 16 + pad if pos in ("bl", "tl") else sw - 16 - pad - w
        y0 = 16 + pad if pos in ("tl", "tr") else sh - 16 - pad - h
        self._box(x0 - pad, y0 - pad, x0 + w + pad, y0 + h + pad)
        for i, direction in enumerate(gm_extras.FNF_DIRS):
            cx, cy = x0 + i * (cell + gap) + cell / 2, y0 + cell / 2
            on, color = lanes.down[i], gm_extras.FNF_COLORS[i]
            self.canvas.create_polygon(*gm_extras.arrow_points(direction, cx, cy, cell * 0.46),
                                       fill=color if on else "#1f2937",
                                       outline="#ffffff" if on else color, width=2)
            self._text(cx, y0 + cell + 4 * k, f"{labels[i]}  {lanes.count[i]}", size=10,
                       anchor="n", bold=True)
        self._text(x0, y0 + cell + 28 * k,
                   f"KPS {lanes.kps()}   pico {lanes.peak}   total {lanes.total}",
                   size=11, color="#facc15", bold=True)

    def _game_mem_mb(self):
        now = time.time()
        if now - self._mem_at > 2.0:                       # a cada 2 s, não a cada quadro
            self._mem_at = now
            try:
                self._mem_mb = process_mem_mb(self.settings["game"])
            except Exception:
                self._mem_mb = 0.0
        return self._mem_mb

    def _client_box(self, sw, sh, x_pct, y_pct, label, value, color, accent, flat):
        k = self.settings["overlay"]["scale"] / 100.0
        size = max(6, int(11 * k))
        text = f"{label}  {value}" if label else value
        font = ("Consolas", size, "bold")
        tid = self.canvas.create_text(0, 0, text=text, anchor="nw", font=font)
        bb = self.canvas.bbox(tid) or (0, 0, len(text) * size * 0.8, size * 1.6)
        self.canvas.delete(tid)
        w, h = bb[2] - bb[0] + 18 * k, bb[3] - bb[1] + 10 * k
        x, y = gm_extras.anchor_xy(sw, sh, w, h, x_pct, y_pct)
        if flat:
            self.canvas.create_text(x + 1, y + 1, text=text, anchor="nw", fill="#000000", font=font)
            self.canvas.create_text(x, y, text=text, anchor="nw", fill=color, font=font)
        else:
            self._box(x, y, x + w, y + h, fill="#0f0f10", outline="#2a2a2e")
            self.canvas.create_rectangle(x, y, x + 3 * k, y + h, fill=accent, outline=accent)
            self.canvas.create_text(x + 10 * k, y + 5 * k, text=text, anchor="nw", fill=color,
                                    font=font)

    def _client_keys(self, sw, sh, cfg, accent):
        k = self.settings["overlay"]["scale"] / 100.0
        rects, w, h = gm_extras.keystroke_layout(34 * k, 3 * k, cfg["keys_space"], cfg["keys_mouse"],
                                                 cfg["keys_mods"])
        ox, oy = gm_extras.anchor_xy(sw, sh, w, h, cfg["keys_x"], cfg["keys_y"])
        down = self.inputs.down
        for label, rx, ry, rw, rh in rects:
            on = down.get(label, False)
            fg = "#0b0b0c" if on else "#ffffff"
            x0, y0 = ox + rx, oy + ry
            self._box(x0, y0, x0 + rw, y0 + rh, fill="#ffffff" if on else "#0f0f10",
                      outline=accent if on else "#2a2a2e")
            cx, cy = x0 + rw / 2, y0 + rh / 2
            if label in ("LMB", "RMB") and cfg["keys_cps"]:
                self._text(cx, cy - 7 * k, label, size=9, color=fg, anchor="center", bold=True)
                self._text(cx, cy + 8 * k, f"{self.inputs.cps(label)} CPS", size=8, color=fg,
                           anchor="center", bold=True)
            else:
                self._text(cx, cy, label, size=13 if len(label) == 1 else 9, color=fg,
                           anchor="center", bold=True)

    def _draw_client(self, sw, sh):
        cfg = self.settings["client"]
        accent = HUD_COLORS.get(cfg["accent"], "#22d3ee")
        flat = cfg["style"] == "text"
        st, li = self.stats, self.inputs
        for key, _label in gm_extras.CLIENT_TEXT_MODULES:
            if not cfg.get(f"{key}_on"):
                continue
            ping = getattr(st, "ping", None)
            label, value = gm_extras.module_parts(
                key, cps=(li.cps("LMB"), li.cps("RMB")), ping=ping,
                cpu=getattr(st, "cpu", 0.0), ram=getattr(st, "ram", 0.0),
                gmem_mb=self._game_mem_mb() if key == "gmem" else 0.0,
                session_s=self.session_fn() if self.session_fn else 0,
                clock=time.strftime("%H:%M"))
            color = ping_color(ping) if key == "ping" else "#ffffff"
            self._client_box(sw, sh, cfg[f"{key}_x"], cfg[f"{key}_y"], label, value, color, accent, flat)
        if cfg.get("keys_on"):
            self._client_keys(sw, sh, cfg, accent)

    def _draw_cross(self, cx, cy):
        cfg = self.settings["crosshair"]
        color = HUD_COLORS.get(cfg["color"], "#00ff66")
        size, gap, thick = cfg["size"], cfg["gap"], cfg["thick"]
        c = self.canvas
        if cfg["shape"] == "dot":
            r = max(1, thick + 1)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline=color)
        elif cfg["shape"] == "circle":
            c.create_oval(cx - size, cy - size, cx + size, cy + size, outline=color, width=thick)
            c.create_oval(cx - 1, cy - 1, cx + 1, cy + 1, fill=color, outline=color)
        else:
            parts = [(cx - size, cy, cx - gap, cy), (cx + gap, cy, cx + size, cy),
                     (cx, cy + gap, cx, cy + size)]
            if cfg["shape"] == "cross":
                parts.append((cx, cy - size, cx, cy - gap))
            for x0, y0, x1, y1 in parts:
                c.create_line(x0, y0, x1, y1, fill=color, width=thick)

    def draw(self, cross_center=None):
        if self.canvas is None or not self.visible:
            return
        ov = self.settings["overlay"]
        sw, sh = self._screen()
        k = ov["scale"] / 100.0
        show = ov["show"]
        look = ov["look"]
        self.canvas.delete("all")
        if show["stats"]:
            if look == "Minimal":
                self._draw_stats(sw - 16, 14, "ne", False)
            else:
                self._draw_stats(16, 16 if look != "Competitive" else 90 * k + 40, "nw", True)
        if show["cps"]:
            self._draw_cps(16, 16)
        if show["keys"]:
            if look == "Neon":
                self._draw_keys(sw / 2 - 74 * k, sh - 190 * k, 46, HUD_COLORS["cyan"], True)
            else:
                self._draw_keys(16, sh - 190 * k, 34, "#4f8cff", False)
        if show["mouse"]:
            if look == "Neon":
                self._draw_mouse(sw / 2 - 80 * k, sh - 60 * k)
            else:
                self._draw_mouse(16, sh - 62 * k)
        if show["crosshair"]:
            cx, cy = cross_center or (sw // 2, sh // 2)
            self._draw_cross(cx, cy)
        if show.get("fnf") and gm_extras is not None:
            self._draw_fnf(sw, sh)
        if show.get("client") and gm_extras is not None:
            self._draw_client(sw, sh)

    def hide(self):
        self.set_visible(False)


def undo_brightness(sample, percent, used):
    """Tira da medição o brilho que o próprio programa aplicou (se a captura enxergar)."""
    if sample is None or percent == 100 or used not in ("gamma", "mag"):
        return sample
    if used == "mag":
        scale, offset = _mag_params(percent)
        return tuple(max(0.0, min(255.0, (v / 255.0 - offset) / scale * 255.0)) for v in sample)
    gamma = percent / 100.0
    return tuple(255.0 * (v / 255.0) ** gamma for v in sample)


def foreground_exe():
    """Nome do .exe da janela em primeiro plano (minúsculas), ou ''."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)



def process_path_of(exe_name):
    """Caminho completo do programa aberto com esse nome, ou ''."""
    want = exe_name.lower()
    for pid, name in list_processes().items():
        if name != want:
            continue
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(520)
            size = wintypes.DWORD(520)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value
        finally:
            kernel32.CloseHandle(h)
    return ""


# --------------------------------------------------------------------------
# Brilho automático: mede a claridade da imagem do jogo
# --------------------------------------------------------------------------

try:
    AUTO_W, AUTO_H = 48, 27


    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.SetStretchBltMode.restype = ctypes.c_int
    gdi32.StretchBlt.argtypes = [wintypes.HDC] + [ctypes.c_int] * 4 + [wintypes.HDC] + \
        [ctypes.c_int] * 4 + [wintypes.DWORD]
    gdi32.StretchBlt.restype = wintypes.BOOL
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi32.GetDIBits.restype = ctypes.c_int


    def sample_luma(center_weight=2, whole=False):
        """(média, sombras) de 0 a 255 da janela em primeiro plano, ou None se não deu para ler
        (tela cheia exclusiva e conteúdo protegido costumam vir pretos)."""
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        x, y, w, h = 0, 0, sw, sh
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if not whole and hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            left, top = max(0, rect.left), max(0, rect.top)
            right, bottom = min(sw, rect.right), min(sh, rect.bottom)
            if right - left >= 200 and bottom - top >= 150:
                x, y, w, h = left, top, right - left, bottom - top
        screen = user32.GetDC(None)
        if not screen:
            return None
        memdc = gdi32.CreateCompatibleDC(screen)
        bmp = gdi32.CreateCompatibleBitmap(screen, AUTO_W, AUTO_H) if memdc else None
        old = None
        try:
            if not (memdc and bmp):
                return None
            old = gdi32.SelectObject(memdc, bmp)
            gdi32.SetStretchBltMode(memdc, 4)  # HALFTONE: média dos pixels ao reduzir
            if not gdi32.StretchBlt(memdc, 0, 0, AUTO_W, AUTO_H, screen, x, y, w, h, 0x00CC0020):
                return None
            info = BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.bmiHeader.biWidth = AUTO_W
            info.bmiHeader.biHeight = -AUTO_H  # de cima para baixo
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            buf = (ctypes.c_ubyte * (AUTO_W * AUTO_H * 4))()
            if gdi32.GetDIBits(memdc, bmp, 0, AUTO_H, buf, ctypes.byref(info), 0) == 0:
                return None
            data = bytes(buf)
        finally:
            if old:
                gdi32.SelectObject(memdc, old)
            if bmp:
                gdi32.DeleteObject(bmp)
            if memdc:
                gdi32.DeleteDC(memdc)
            user32.ReleaseDC(None, screen)
        if not any(data):
            return None
        blue, green, red = data[0::4], data[1::4], data[2::4]
        weighted = []
        for i, (r, g, b) in enumerate(zip(red, green, blue)):
            luma = (299 * r + 587 * g + 114 * b) // 1000
            weighted.append(luma)
            row, col = divmod(i, AUTO_W)
            if AUTO_W // 4 <= col < AUTO_W * 3 // 4 and AUTO_H // 4 <= row < AUTO_H * 3 // 4:
                for _extra in range(max(1, int(center_weight)) - 1):
                    weighted.append(luma)  # o centro (mira) pesa mais
        weighted.sort()
        mean = sum(weighted) / len(weighted)
        shadow = weighted[int(len(weighted) * 0.35)]  # as sombras pesam mais que o céu/HUD
        return mean, shadow
except Exception as _exc:  # sem captura de tela: o brilho automático usa o valor fixo
    write_error_log(tr("Captura de tela indisponível: ") + repr(_exc))

    def sample_luma(center_weight=2, whole=False):
        return None


MEASURE_SHADOW_WEIGHT = {"shadow": 0.8, "mix": 0.6, "mean": 0.0}


class FlashGuard:
    """Protege dos flashes: se a imagem clareia de repente, a tela escurece na hora e volta
    devagar. Cena clara que continua clara não conta (a referência acompanha a imagem)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.ref = None      # claridade "normal" recente da cena (0 a 255)
        self.dim = 0.0       # quanto estamos escurecendo agora (pontos de %)
        self.luma = 0.0
        self.last_ok = 0.0

    def update(self, sample, now, dt, d):
        """sample = (média, sombras) ou None. Retorna quanto escurecer (pontos de %) ou None."""
        dt = max(0.01, min(0.5, dt))
        release = 10.0 + 1.5 * max(1.0, min(100.0, float(d["flash_release"])))   # pontos/s
        if sample is None:
            if now - self.last_ok < 2.0:
                self.dim = max(0.0, self.dim - release * dt)
                return self.dim
            return None
        self.last_ok = now
        weight = MEASURE_SHADOW_WEIGHT.get(d["measure"], 0.6)
        raw = (1.0 - weight) * sample[0] + weight * sample[1]
        self.luma = raw
        if self.ref is None:
            self.ref = raw
        jump = raw - self.ref
        threshold = 90.0 - 0.75 * max(0.0, min(100.0, float(d["flash_sens"])))   # 90 a 15
        want = 0.0
        if jump > threshold:
            want = min(1.0, (jump - threshold) / 60.0) * float(d["flash_amount"])
        if want >= self.dim:
            self.dim = want                                    # ataque imediato
        else:
            self.dim = max(want, self.dim - release * dt)      # volta devagar
        tau = 2.0 if raw > self.ref else 0.6
        self.ref += (raw - self.ref) * (1.0 - math.exp(-dt / tau))
        return self.dim


atexit.register(restore_brightness)
atexit.register(shader_clear)


# --------------------------------------------------------------------------
# QoS (prioridade de rede) — feito aqui mesmo, sem janela de cmd/PowerShell
# --------------------------------------------------------------------------

QOS_POLICY = "GameModeLite-QoS"
QOS_REG_PATH = "SOFTWARE\\Policies\\Microsoft\\Windows\\QoS\\" + QOS_POLICY
CREATE_NO_WINDOW = 0x08000000


def is_frozen():
    """True quando o programa roda como .exe (PyInstaller ou Nuitka) e não como script."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


SEE_MASK_NOCLOSEPROCESS = 0x00000040
ERROR_CANCELLED = 1223
WAIT_TIMEOUT = 0x00000102

shell32 = ctypes.WinDLL("shell32", use_last_error=True)


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
    ]


shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.ShellExecuteExW.restype = wintypes.BOOL
shell32.IsUserAnAdmin.argtypes = []
shell32.IsUserAnAdmin.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL


def _ps_quote(text):
    return text.replace("'", "''")


def run_powershell(body, elevate, timeout=90):
    """Roda um script do PowerShell sem mostrar janela. Retorna (ok, texto).
    Com elevate=True o Windows pede permissão de administrador (UAC) uma vez."""
    out_path = os.path.join(tempfile.gettempdir(),
                            f"gamemode_ps_{os.getpid()}_{int(time.time() * 1000)}.txt")
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$out = '{_ps_quote(out_path)}'\n"
        "$extra = ''\n"
        "try {\n" + body + "\nSet-Content -LiteralPath $out -Value ('OK' + $extra) "
        "-Encoding UTF8\n} catch {\nSet-Content -LiteralPath $out "
        "-Value ('ERRO: ' + $_.Exception.Message) -Encoding UTF8\n}\n")
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                       "WindowsPowerShell", "v1.0", "powershell.exe")
    # O script vai como texto legível em -Command (nada de comando codificado).
    args = ["-NoProfile", "-NonInteractive", "-Command", script]
    try:
        if elevate and not shell32.IsUserAnAdmin():
            info = SHELLEXECUTEINFOW()
            info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
            info.fMask = SEE_MASK_NOCLOSEPROCESS
            info.lpVerb = "runas"
            info.lpFile = exe
            info.lpParameters = subprocess.list2cmdline(args)
            info.nShow = 0  # SW_HIDE
            if not shell32.ShellExecuteExW(ctypes.byref(info)):
                if ctypes.get_last_error() == ERROR_CANCELLED:
                    return False, tr("Você cancelou o pedido de administrador do Windows. Nada foi alterado.")
                return False, tr('Não consegui pedir permissão de administrador (erro {}).').format(ctypes.get_last_error())
            try:
                if kernel32.WaitForSingleObject(info.hProcess, timeout * 1000) == WAIT_TIMEOUT:
                    return False, tr("O PowerShell demorou demais para responder.")
            finally:
                kernel32.CloseHandle(info.hProcess)
        else:
            subprocess.run([exe] + args, creationflags=CREATE_NO_WINDOW,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=timeout)
        try:
            with open(out_path, encoding="utf-8-sig") as f:
                text = f.read().strip()
        except OSError:
            return False, tr("O PowerShell não devolveu resultado (o Windows pode ter bloqueado).")
        if text.startswith("ERRO"):
            return False, text
        return True, text
    except subprocess.TimeoutExpired:
        return False, tr("O PowerShell demorou demais para responder.")
    except OSError as exc:
        return False, tr('Não consegui abrir o PowerShell: {}').format(exc)
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass


_QOS_REMOVE_PS = (
    "$name = '" + QOS_POLICY + "'\n"
    "Get-NetQosPolicy -Name $name -ErrorAction SilentlyContinue | "
    "Remove-NetQosPolicy -Confirm:$false -ErrorAction SilentlyContinue\n"
    "Get-NetQosPolicy -PolicyStore ActiveStore -Name $name -ErrorAction SilentlyContinue | "
    "Remove-NetQosPolicy -PolicyStore ActiveStore -Confirm:$false -ErrorAction SilentlyContinue\n")
_QOS_NLA_PATH = r"HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\QoS"


def qos_apply(game, dscp, all_net):
    """Retorna (ok, [(nivel, texto)], criou_chave_nla)."""
    game = game.strip()
    if not game:
        return False, [("warn", tr("Escolha o programa do jogo em Opções."))], False
    g = _ps_quote(game)
    body = _QOS_REMOVE_PS + (
        f"New-NetQosPolicy -Name $name -AppPathNameMatchCondition '{g}' "
        f"-DSCPAction {int(dscp)} -NetworkProfile All | Out-Null\n"
        f"try {{ New-NetQosPolicy -PolicyStore ActiveStore -Name $name "
        f"-AppPathNameMatchCondition '{g}' -DSCPAction {int(dscp)} -NetworkProfile All "
        f"| Out-Null }} catch {{ }}\n")
    if all_net:
        body += (
            f"$p = '{_QOS_NLA_PATH}'\n"
            "if (-not (Test-Path $p)) { New-Item -Path $p -Force | Out-Null }\n"
            "$had = $null -ne (Get-ItemProperty -Path $p -Name 'Do not use NLA' "
            "-ErrorAction SilentlyContinue)\n"
            "New-ItemProperty -Path $p -Name 'Do not use NLA' -Value '1' "
            "-PropertyType String -Force | Out-Null\n"
            "if (-not $had) { $extra = '|NLA_NEW' }\n")
    ok, text = run_powershell(body, elevate=True)
    if not ok:
        return False, [("warn", tr("QoS não foi aplicado. ") + text)], False
    msgs = [("ok", tr('QoS ativo para {} com DSCP {}.').format(game, int(dscp)))]
    if all_net:
        msgs.append(("info", tr("Vale também em redes de casa. Se não fizer efeito, reinicie o PC uma vez.")))
    return True, msgs, "NLA_NEW" in text


def qos_remove(remove_nla):
    """Retorna (ok, [(nivel, texto)])."""
    body = _QOS_REMOVE_PS
    if remove_nla:
        body += (f"Remove-ItemProperty -Path '{_QOS_NLA_PATH}' -Name 'Do not use NLA' "
                 "-ErrorAction SilentlyContinue\n")
    ok, text = run_powershell(body, elevate=True)
    if not ok:
        return False, [("warn", tr("Não consegui remover o QoS. ") + text)]
    return True, [("ok", tr("QoS removido."))]


def qos_status():
    """Lê do registro (sem administrador): {'active': bool, 'dscp': int|None}."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, QOS_REG_PATH) as key:
            try:
                dscp = int(str(winreg.QueryValueEx(key, "DSCP Value")[0]).strip())
            except (OSError, ValueError):
                dscp = None
            return {"active": True, "dscp": dscp}
    except (OSError, ImportError):
        return {"active": False, "dscp": None}


def _detach_console():
    """Sem janela de cmd: se abriu pelo python.exe, reabre pelo pythonw.exe (sem console) e sai.
    Se não der, esconde o console (ele some da barra de tarefas também)."""
    if "--console" in sys.argv or is_frozen():
        return
    try:
        kernel32.GetConsoleWindow.argtypes = []
        kernel32.GetConsoleWindow.restype = wintypes.HWND
        hwnd = kernel32.GetConsoleWindow()
    except Exception:
        return
    if not hwnd:
        return
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if (os.path.basename(exe).lower() == "python.exe" and os.path.exists(pyw)
            and "--detached" not in sys.argv):
        try:
            subprocess.Popen(
                [pyw, os.path.abspath(__file__)] + sys.argv[1:] + ["--detached"],
                creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | NEW_PROCESS_GROUP
                close_fds=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            sys.exit(0)
        except OSError:
            pass
    try:
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass



# --------------------------------------------------------------------------
# Game Mode extra (do Lyre): GPU de alto desempenho para o Roblox e ajustes de jogo do Windows
# --------------------------------------------------------------------------

GPU_PREF_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
GPU_PREF_VALUE = "GpuPreference=2;"   # 2 = alto desempenho


def roblox_exes():
    """RobloxPlayerBeta.exe de cada versão instalada."""
    import glob
    roots = [os.path.join(os.environ.get(var, ""), *sub, "Versions") for var, sub in
             (("LOCALAPPDATA", ("Roblox",)), ("ProgramFiles(x86)", ("Roblox",)),
              ("ProgramFiles", ("Roblox",)))]
    found = []
    for root in roots:
        if root and os.path.isdir(root):
            found += glob.glob(os.path.join(root, "*", "RobloxPlayerBeta.exe"))
    return sorted(set(found))


def gpu_pref_apply(paths):
    """Põe a GPU de alto desempenho para cada exe (preferência do Windows, só do seu usuário).
    Retorna os caminhos que foram mudados agora."""
    import winreg
    changed = []
    access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, GPU_PREF_KEY, 0, access) as key:
        for path in paths:
            try:
                current = winreg.QueryValueEx(key, path)[0]
            except OSError:
                current = None
            if current != GPU_PREF_VALUE:
                winreg.SetValueEx(key, path, 0, winreg.REG_SZ, GPU_PREF_VALUE)
                changed.append(path)
    return changed


def gpu_pref_clear(paths):
    """Tira a preferência dos caminhos que o programa mudou. Retorna quantos tirou."""
    import winreg
    removed = 0
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, GPU_PREF_KEY, 0, winreg.KEY_SET_VALUE) as key:
            for path in paths:
                try:
                    winreg.DeleteValue(key, path)
                    removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    return removed


FSO_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"


def fso_apply(paths, off):
    """Desliga (off=True) ou religa as otimizações de tela cheia do Windows para cada .exe, só do seu
    usuário e sem apagar outras opções do programa. Retorna os caminhos que mudaram."""
    import winreg
    changed = []
    access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, FSO_KEY, 0, access) as key:
        for path in paths:
            try:
                current = winreg.QueryValueEx(key, path)[0]
            except OSError:
                current = ""
            new = gm_extras.layers_with(current, gm_extras.FSO_FLAG, off)
            if new == current:
                continue
            if new:
                winreg.SetValueEx(key, path, 0, winreg.REG_SZ, new)
            else:
                try:
                    winreg.DeleteValue(key, path)
                except OSError:
                    pass
            changed.append(path)
    return changed


def process_mem_mb(exe_name):
    """RAM (MB) usada pelo(s) programa(s) com esse nome. 0 se não achar."""
    want = exe_name.lower()
    total = 0
    for pid, name in list_processes().items():
        if name != want:
            continue
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | 0x0010, False, pid)
        if not h:
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            continue
        try:
            total += working_set(h)
        finally:
            kernel32.CloseHandle(h)
    return total / (1024 * 1024)


def gpu_targets_for(game, settings):
    """Caminhos dos .exe do jogo para a preferência de GPU. Roblox: todas as versões instaladas.
    Outros jogos: o caminho guardado no perfil (ou achado com o jogo aberto)."""
    game = (game or "").lower()
    if game == "robloxplayerbeta.exe":
        return roblox_exes()
    prof = gm_extras.find_profile(settings.get("profiles", []), game) if gm_extras else None
    path = (prof or {}).get("path", "")
    if not path or not os.path.isfile(path):
        path = process_path_of(game)
        if path and prof is not None:
            prof["path"] = path
    return [path] if path and os.path.isfile(path) else []


WIN_TWEAK_ROOT = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
WIN_TWEAKS = [   # (subchave, nome, valor novo, tipo)
    ("", "SystemResponsiveness", 0, "DWord"),
    ("", "NetworkThrottlingIndex", 0xFFFFFFFF, "DWord"),
    ("Tasks\\Games", "GPU Priority", 8, "DWord"),
    ("Tasks\\Games", "Priority", 6, "DWord"),
    ("Tasks\\Games", "Scheduling Category", "High", "String"),
    ("Tasks\\Games", "SFIO Priority", "High", "String"),
]


def _tweak_id(sub, name):
    return f"{sub}|{name}"


def win_tweaks_read():
    """Valores atuais (sem precisar de administrador): {'sub|nome': valor ou None}."""
    import winreg
    out = {}
    for sub, name, _value, _kind in WIN_TWEAKS:
        path = WIN_TWEAK_ROOT + ("\\" + sub if sub else "")
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                out[_tweak_id(sub, name)] = winreg.QueryValueEx(key, name)[0]
        except OSError:
            out[_tweak_id(sub, name)] = None
    return out


def win_tweaks_active():
    try:
        current = win_tweaks_read()
    except Exception:
        return False
    return all(current.get(_tweak_id(sub, name)) == value for sub, name, value, _k in WIN_TWEAKS)


# Tarefas que precisam de administrador: o próprio programa se abre de novo com permissão (o Windows
# mostra o aviso UAC), faz UMA tarefa fixa e fecha. Não usa PowerShell e não recebe caminhos de fora:
# só "tweaks" existe, e ela só mexe nos 6 valores de WIN_TWEAKS.
ADMIN_OK, ADMIN_BAD_ARGS, ADMIN_REG_ERROR, ADMIN_DENIED = 0, 2, 3, 5
ADMIN_TEXT = {ADMIN_BAD_ARGS: tr("pedido inválido"), ADMIN_REG_ERROR: tr("o Windows recusou mexer no registro"),
              ADMIN_DENIED: tr("acesso negado")}
_TOKEN_TEXT = re.compile(r"^[A-Za-z0-9 ._-]{0,64}$")


def tweak_token(value):
    """Valor do registro -> texto curto para a linha de comando: 'd' apagar, 'i123' número, 'sHigh' texto."""
    if value is None:
        return "d"
    if isinstance(value, int):
        return f"i{int(value)}"
    return f"s{value}"


def parse_tweak_token(token):
    """('d', None) | ('i', número) | ('s', texto) | None se o texto não presta."""
    if token == "d":
        return ("d", None)
    if len(token) >= 2 and token[0] == "i" and token[1:].isdigit() and int(token[1:]) <= 0xFFFFFFFF:
        return ("i", int(token[1:]))
    if token[:1] == "s" and _TOKEN_TEXT.match(token[1:]):
        return ("s", token[1:])
    return None


def win_tweaks_write(tokens):
    """Escreve ou apaga os valores de WIN_TWEAKS, na ordem. Precisa de administrador. Retorna o código."""
    import winreg
    if len(tokens) != len(WIN_TWEAKS):
        return ADMIN_BAD_ARGS
    parsed = [parse_tweak_token(t) for t in tokens]
    if None in parsed:
        return ADMIN_BAD_ARGS
    access = winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY
    try:
        for (sub, name, _value, _kind), (kind, val) in zip(WIN_TWEAKS, parsed):
            path = WIN_TWEAK_ROOT + ("\\" + sub if sub else "")
            if kind == "d":
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, access) as key:
                        winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            else:
                with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, access) as key:
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD if kind == "i" else winreg.REG_SZ, val)
    except PermissionError:
        return ADMIN_DENIED
    except OSError:
        return ADMIN_REG_ERROR
    return ADMIN_OK


def admin_job_main(argv):
    """Roda no processo elevado: --admin-job <tarefa> <argumentos...>. Retorna o código de saída."""
    try:
        i = argv.index("--admin-job")
        job, rest = argv[i + 1], argv[i + 2:]
    except (ValueError, IndexError):
        return ADMIN_BAD_ARGS
    if job == "tweaks":
        return win_tweaks_write(rest)
    return ADMIN_BAD_ARGS


def self_command():
    """(programa, argumentos fixos) para abrir este mesmo programa de novo."""
    if is_frozen():
        return sys.executable, []
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return (pyw if os.path.exists(pyw) else exe), [os.path.abspath(__file__)]


def _admin_result(code):
    if code == ADMIN_OK:
        return True, "OK"
    return False, tr("ERRO: ") + ADMIN_TEXT.get(code, f"código {code}")


def run_admin_job(job, tokens, timeout=60):
    """Faz uma tarefa fixa como administrador. Retorna (ok, texto). O Windows pede permissão (UAC)."""
    tokens = list(tokens)
    if shell32.IsUserAnAdmin():
        return _admin_result(admin_job_main(["--admin-job", job] + tokens))
    exe, base = self_command()
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = exe
    info.lpParameters = subprocess.list2cmdline(base + ["--admin-job", job] + tokens)
    info.nShow = 0  # SW_HIDE
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        if ctypes.get_last_error() == ERROR_CANCELLED:
            return False, tr("Você cancelou o pedido de administrador do Windows. Nada foi alterado.")
        return False, tr('Não consegui pedir permissão de administrador (erro {}).').format(ctypes.get_last_error())
    try:
        if kernel32.WaitForSingleObject(info.hProcess, timeout * 1000) == WAIT_TIMEOUT:
            return False, tr("A tarefa de administrador demorou demais para responder.")
        code = wintypes.DWORD(1)
        kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    finally:
        kernel32.CloseHandle(info.hProcess)
    return _admin_result(code.value)


def win_tweaks_apply():
    """Aplica os ajustes (pede administrador). Retorna (ok, [(nivel, texto)])."""
    ok, text = run_admin_job("tweaks", [tweak_token(value) for _s, _n, value, _k in WIN_TWEAKS])
    if not ok:
        return False, [("warn", tr("Ajustes do Windows não aplicados. ") + text)]
    return True, [("ok", tr("Ajustes de jogo do Windows aplicados. Valem para novos jogos; "
                         "reiniciar o PC garante."))]


def win_tweaks_restore(backup):
    """Volta aos valores de antes (backup) ou apaga o que não existia."""
    tokens = [tweak_token((backup or {}).get(_tweak_id(sub, name))) for sub, name, _v, _k in WIN_TWEAKS]
    ok, text = run_admin_job("tweaks", tokens)
    if not ok:
        return False, [("warn", tr("Não consegui voltar os ajustes do Windows. ") + text)]
    return True, [("ok", tr("Ajustes de jogo do Windows desfeitos (valores de antes)."))]


BRIGHT_KEYS = [("none", tr("Nenhuma"), 0), ("f9", "F9", 0x78), ("f10", "F10", 0x79),
               ("f11", "F11", 0x7A), ("f12", "F12", 0x7B), ("mouse5", "Mouse 5", 0x06)]
BRIGHT_LABELS = [(k, label) for k, label, _vk in BRIGHT_KEYS]
BRIGHT_VK = {k: vk for k, _label, vk in BRIGHT_KEYS}
MEASURE_LABELS = [("mix", tr("Equilibrado")), ("shadow", tr("Sombras")), ("mean", tr("Média"))]
CENTER_LABELS = [("1", tr("Igual")), ("2", tr("Dobro")), ("3", tr("Triplo"))]
AREA_LABELS = [("window", tr("Janela do jogo")), ("screen", tr("Tela inteira"))]
FLASH_PRESETS = {
    "Suave": {"flash_sens": 40, "flash_amount": 20, "flash_release": 30},
    "Normal": {"flash_sens": 60, "flash_amount": 30, "flash_release": 40},
    "Forte": {"flash_sens": 85, "flash_amount": 45, "flash_release": 60},
}
BRIGHT_PRESETS = [(tr("Normal"), 100), (tr("Claro"), 130), (tr("Mais claro"), 160), (tr("Máximo"), 200)]



def reason(err):
    if err == ERROR_ACCESS_DENIED:
        return tr("acesso negado (o Windows ou um anti-cheat bloqueou)")
    if err == ERROR_INVALID_PARAMETER:
        return tr("não suportado nesta versão do Windows")
    return tr('erro {} do Windows').format(err)


# --------------------------------------------------------------------------
# Lógica do Game Mode
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Apoio: janela, tempo, programas abertos, recuperação de sessão, iniciar com o Windows
# --------------------------------------------------------------------------

def fit_geometry(saved, sw, sh, default_w=1100, default_h=780, min_w=960, min_h=680):
    """Tamanho e posição da janela que SEMPRE cabem na tela. Retorna (w, h, x, y)."""
    max_w, max_h = max(400, sw - 20), max(300, sh - 60)
    w = saved.get("w") or default_w
    h = saved.get("h") or default_h
    w = max(min(min_w, max_w), min(int(w), max_w))
    h = max(min(min_h, max_h), min(int(h), max_h))
    x, y = saved.get("x", -1), saved.get("y", -1)
    if (not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0
            or x + 100 > sw or y + 60 > sh):
        x, y = (sw - w) // 2, (sh - h) // 3  # sem posição guardada (ou fora da tela): centraliza
    x = max(0, min(x, sw - w))
    y = max(0, min(y, sh - h - 40))
    return w, h, x, y


def fmt_duration(seconds):
    s = int(seconds)
    if s < 60:
        return tr("menos de 1 min")
    minutes = s // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return tr('{} h {} min').format(hours, f'{minutes:02d}')


NOT_GAMES = {
    "pythonw.exe", "python.exe", "conhost.exe", "runtimebroker.exe", "searchhost.exe",
    "applicationframehost.exe", "textinputhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "taskhostw.exe", "backgroundtaskhost.exe", "dllhost.exe",
    "wmiprvse.exe", "securityhealthsystray.exe", "msedgewebview2.exe", "lockapp.exe",
    "searchindexer.exe", "spoolsv.exe", "wudfhost.exe", "system idle process",
    "secure system", "memory compression",
}


def running_program_names(exclude=()):
    """Programas (.exe) abertos agora, sem os do sistema e os protegidos. Ordem alfabética."""
    skip = {e.lower() for e in exclude}
    return sorted({n for n in list_processes().values() if n.endswith(".exe") and n not in skip})


def session_path():
    return os.path.join(os.path.dirname(SETTINGS_PATH), "session.json")


def boot_time():
    """Momento (aproximado) em que o Windows ligou. Muda se o PC reiniciar."""
    try:
        return int(time.time() - kernel32.GetTickCount64() / 1000.0)
    except Exception:
        return 0


def save_session(saved):
    """Guarda em arquivo o que o Game Mode alterou, para desfazer se o programa fechar à força."""
    path = session_path()
    if not saved:
        try:
            os.unlink(path)
        except OSError:
            pass
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {"boot": boot_time(), "pids": {str(pid): info for pid, info in saved.items()}}
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        pass


def restore_process(pid, info):
    """Devolve um processo ao estado de antes. Retorna True se conseguiu."""
    h, _err = open_process(pid)
    if not h:
        return False
    try:
        if info.get("priority"):
            set_priority(h, info["priority"])
        if info.get("eco"):
            set_eco(h, "default")
        if info.get("mem"):
            set_memprio(h, MEMORY_PRIORITY_NORMAL)
        if info.get("io") is not None:
            set_io_priority(h, info["io"])
        if info.get("affinity"):
            kernel32.SetProcessAffinityMask(h, info["affinity"])
        return True
    finally:
        kernel32.CloseHandle(h)



# --- plano de energia ---------------------------------------------------------------------
try:
    import uuid

    powrprof = ctypes.WinDLL("powrprof")


    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                    ("Data4", ctypes.c_ubyte * 8)]


    powrprof.PowerGetActiveScheme.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(GUID))]
    powrprof.PowerGetActiveScheme.restype = wintypes.DWORD
    powrprof.PowerSetActiveScheme.argtypes = [ctypes.c_void_p, ctypes.POINTER(GUID)]
    powrprof.PowerSetActiveScheme.restype = wintypes.DWORD
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    HIGH_PERFORMANCE_PLAN = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


    def get_power_scheme():
        ptr = ctypes.POINTER(GUID)()
        if powrprof.PowerGetActiveScheme(None, ctypes.byref(ptr)) != 0 or not ptr:
            return None
        try:
            return str(uuid.UUID(bytes_le=ctypes.string_at(ptr, 16)))
        finally:
            kernel32.LocalFree(ptr)


    def set_power_scheme(text):
        try:
            guid = GUID.from_buffer_copy(uuid.UUID(text).bytes_le)
        except ValueError:
            return False
        return powrprof.PowerSetActiveScheme(None, ctypes.byref(guid)) == 0
except Exception as _exc:  # sem plano de energia: desliga só este recurso
    write_error_log(tr("Plano de energia indisponível: ") + repr(_exc))

    def get_power_scheme():
        return None

    def set_power_scheme(text):
        return False


def power_state_path():
    return os.path.join(os.path.dirname(SETTINGS_PATH), "power.json")


def save_power_state(prev):
    try:
        os.makedirs(os.path.dirname(power_state_path()), exist_ok=True)
        with open(power_state_path(), "w", encoding="utf-8") as f:
            json.dump({"prev": prev}, f)
    except OSError:
        pass


def clear_power_state():
    try:
        os.unlink(power_state_path())
    except OSError:
        pass


def recover_power():
    """Se o programa fechou à força com o plano Alto desempenho ligado, volta ao plano anterior."""
    try:
        with open(power_state_path(), encoding="utf-8") as f:
            prev = json.load(f).get("prev")
    except (OSError, ValueError, AttributeError):
        return False
    clear_power_state()
    if prev and get_power_scheme() == HIGH_PERFORMANCE_PLAN:
        return set_power_scheme(prev)
    return False


def recover_session():
    """Restaura o que uma sessão anterior alterou e não devolveu (programa fechado à força,
    queda de energia...). Retorna (restaurados, encontrados)."""
    try:
        recover_power()
    except Exception:
        pass
    path = session_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return 0, 0
    try:
        os.unlink(path)
    except OSError:
        pass
    if not isinstance(data, dict) or not isinstance(data.get("pids"), dict):
        return 0, 0
    try:
        if abs(int(data.get("boot", 0)) - boot_time()) > 120:
            return 0, 0  # o PC reiniciou desde então: os processos antigos já não existem
    except (TypeError, ValueError):
        return 0, 0
    current = list_processes()
    done = total = 0
    for pid_text, info in data["pids"].items():
        try:
            pid, name = int(pid_text), info["name"]
        except (ValueError, TypeError, KeyError):
            continue
        total += 1
        if current.get(pid) != name:
            continue  # fechou, ou o número foi reaproveitado por outro programa
        if restore_process(pid, info):
            done += 1
    return done, total


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "GameModeLite"


def launcher_command():
    if is_frozen():  # rodando como .exe: o próprio .exe é o atalho
        return f'"{sys.executable}" --minimized'
    here = os.path.dirname(os.path.abspath(__file__))
    launcher = os.path.join(here, "gamemode_gui.pyw")
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(exe):
        exe = sys.executable
    target = launcher if os.path.exists(launcher) else os.path.abspath(__file__)
    return f'"{exe}" "{target}" --minimized'


def autostart_enabled():
    """O programa está na lista de 'iniciar com o Windows' deste usuário?"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, RUN_NAME)[0])
    except (OSError, ImportError):
        return False


def set_autostart(enabled):
    """Liga/desliga o início com o Windows (só deste usuário, sem administrador)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, launcher_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_NAME)
                except FileNotFoundError:
                    pass
        return True, ""
    except (OSError, ImportError) as exc:
        return False, str(exc)


class Report:
    """Resultado de uma passada do apply()."""

    def __init__(self):
        self.game = []                       # (ok, texto)
        self.calmed = Counter()
        self.eco_fail = defaultdict(set)
        self.mem_fail = defaultdict(set)
        self.calm_fail = defaultdict(set)
        self.trim_ok = 0
        self.freed = 0
        self.skipped = 0

    def empty(self):
        return not (self.game or self.calmed or self.calm_fail or self.eco_fail
                    or self.mem_fail or self.trim_ok or self.skipped)


class GameMode:
    def __init__(self, settings):
        self.game_label = settings["game"]
        self.game = settings["game"].lower()
        self.calm = {n.lower() for n in settings["calm"]}
        self.protect = {n.lower() for n in settings["protect"]}
        self.game_priority = HIGH_PRIORITY_CLASS if settings["high"] else ABOVE_NORMAL_PRIORITY_CLASS
        self.trim = settings["trim"]
        self.trim_all = settings["trim_all"]
        self.eco = settings["eco"]
        self.mem_priority = settings["mem_priority"]
        self.io_priority = settings.get("io_priority", True)
        self.limit_cpu = settings.get("limit_cpu", False)
        self.power_plan = settings.get("power_plan", True)
        self.gpu_pref = settings.get("gpu_pref", False)
        self._settings_ref = settings
        self.power_prev = None   # plano de energia de antes do jogo (None = não mexemos)

        self.own_pid = os.getpid()
        self.saved = {}      # pid -> {"name", "priority", "eco", "mem"}
        self.done = set()    # pids já tratados (com sucesso ou não)
        self.apps = {}       # nome -> {"pids", "slowed", "freed", "eco", "mem"}
        self.active = False
        self.game_ok = False
        self.total_freed = 0
        self.in_use = set()  # apps da lista que estão em uso agora (voltam ao normal)

    def _entry(self, name, pid):
        e = self.apps.setdefault(
            name, {"pids": set(), "slowed": set(), "freed": 0, "eco": False, "mem": False,
                   "io": False, "cpu": False})
        e["pids"].add(pid)
        return e

    # ---- aplicar -----------------------------------------------------

    def apply(self, procs):
        alive = set(procs)
        self.done &= alive
        for pid in list(self.saved):
            if procs.get(pid) != self.saved[pid]["name"]:
                del self.saved[pid]
        for name in list(self.apps):
            e = self.apps[name]
            e["pids"] &= alive
            e["slowed"] &= alive
            if not e["pids"]:
                del self.apps[name]

        rep = Report()
        for pid, name in procs.items():
            if pid in self.done or pid == self.own_pid:
                continue
            self.done.add(pid)

            if name == self.game:
                self._boost_game(pid, rep)
            elif name in self.protect:
                continue
            else:
                is_calm = name in self.calm
                if is_calm and name in self.in_use:
                    continue  # está em uso agora: fica normal até você sair dele
                wants_trim = self.trim and (is_calm or self.trim_all)
                if is_calm or wants_trim:
                    self._calm_or_trim(pid, name, is_calm, wants_trim, rep)

        self.total_freed += rep.freed
        return rep

    def _boost_game(self, pid, rep):
        h, err = open_process(pid)
        if not h:
            rep.game.append((False, tr('não consegui abrir o processo — {}').format(reason(err))))
            return
        try:
            original = get_priority(h)
            ok, err = set_priority(h, self.game_priority)
            if not ok:
                rep.game.append((False, tr('não consegui subir a prioridade — {}').format(reason(err))))
                return
            label = tr("ALTA") if self.game_priority == HIGH_PRIORITY_CLASS else tr("ACIMA DO NORMAL")
            text = tr('prioridade {}').format(label)
            eco_changed = False
            if self.eco:
                ok, err = set_eco(h, "off")
                if ok:
                    eco_changed = True
                    text += tr(" + modo de eficiência desativado")
                else:
                    text += tr(' (modo de eficiência não alterado: {})').format(reason(err))
            self.saved[pid] = {"name": self.game, "priority": original,
                               "eco": eco_changed, "mem": False}
            self.game_ok = True
            rep.game.append((True, text))
        finally:
            kernel32.CloseHandle(h)

    def _calm_or_trim(self, pid, name, is_calm, wants_trim, rep):
        h, err = open_process(pid)
        if not h:
            if is_calm:
                rep.calm_fail[reason(err)].add(name)
            else:
                rep.skipped += 1
            return
        try:
            if is_calm:
                original = get_priority(h)
                ok, err = set_priority(h, BELOW_NORMAL_PRIORITY_CLASS)
                if ok:
                    eco_changed = mem_changed = False
                    if self.eco:
                        eco_changed, err_eco = set_eco(h, "on")
                        if not eco_changed:
                            rep.eco_fail[reason(err_eco)].add(name)
                    if self.mem_priority:
                        mem_changed, err_mem = set_memprio(h, MEMORY_PRIORITY_VERY_LOW)
                        if not mem_changed:
                            rep.mem_fail[reason(err_mem)].add(name)
                    io_before = None
                    if self.io_priority:
                        prev_io = get_io_priority(h)
                        if prev_io is not None and prev_io > IO_VERY_LOW \
                                and set_io_priority(h, IO_VERY_LOW):
                            io_before = prev_io
                    affinity_before = limit_affinity(h) if self.limit_cpu else 0
                    self.saved[pid] = {"name": name, "priority": original,
                                       "eco": eco_changed, "mem": mem_changed,
                                       "io": io_before, "affinity": affinity_before}
                    e = self._entry(name, pid)
                    e["slowed"].add(pid)
                    e["eco"] = e["eco"] or eco_changed
                    e["mem"] = e["mem"] or mem_changed
                    e["io"] = e["io"] or io_before is not None
                    e["cpu"] = e["cpu"] or bool(affinity_before)
                    rep.calmed[name] += 1
                else:
                    rep.calm_fail[reason(err)].add(name)

            if wants_trim:
                freed, ok, err = trim_memory(h)
                if ok:
                    self._entry(name, pid)["freed"] += freed
                    rep.trim_ok += 1
                    rep.freed += freed
                elif is_calm:
                    rep.calm_fail[f"não consegui liberar memória — {reason(err)}"].add(name)
        finally:
            kernel32.CloseHandle(h)

    def set_foreground(self, name, procs):
        """Tira a lentidão do app da lista que está em primeiro plano e volta a
        desacelerar o que acabou de sair de foco. Retorna True se mudou algo."""
        want = name if (name in self.calm and name not in self.protect
                        and name != self.game) else None
        changed = False
        for old in list(self.in_use):
            if old != want:
                self._reslow(old, procs)
                changed = True
        if want and want not in self.in_use:
            self._release(want, procs)
            changed = True
        return changed

    def _release(self, name, procs):
        self.in_use.add(name)
        e = self.apps.get(name)
        if not e:
            return
        for pid in list(e["slowed"]):
            info = self.saved.pop(pid, None)
            if info and procs.get(pid) == name:
                restore_process(pid, info)
            e["slowed"].discard(pid)

    def _reslow(self, name, procs):
        self.in_use.discard(name)
        for pid, n in procs.items():
            if n == name and pid != self.own_pid and pid not in self.saved:
                self.done.add(pid)
                self._calm_or_trim(pid, name, True, False, Report())

    def retrim(self, procs):
        """Libera memória de novo dos apps da lista (a memória volta a crescer)."""
        freed_total = count = 0
        for name, e in self.apps.items():
            for pid in list(e["slowed"]):
                if procs.get(pid) != name:
                    continue
                h, _err = open_process(pid)
                if not h:
                    continue
                try:
                    freed, ok, _err = trim_memory(h)
                    if ok:
                        e["freed"] += freed
                        freed_total += freed
                        count += 1
                finally:
                    kernel32.CloseHandle(h)
        self.total_freed += freed_total
        return freed_total, count

    # ---- plano de energia --------------------------------------------

    def boost_power(self):
        """Liga o plano Alto desempenho enquanto o jogo roda. Retorna (nível, texto) ou None."""
        if not self.power_plan or self.power_prev:
            return None
        try:
            prev = get_power_scheme()
            if prev is None:
                return ("warn", tr("Não consegui ler o plano de energia atual."))
            if prev == HIGH_PERFORMANCE_PLAN:
                return ("info", tr("O plano de energia já é Alto desempenho."))
            if not set_power_scheme(HIGH_PERFORMANCE_PLAN):
                return ("warn", tr("Este PC não tem o plano Alto desempenho (ou o Windows recusou)."))
            self.power_prev = prev
            save_power_state(prev)
            return ("ok", tr("Plano de energia: Alto desempenho (volta ao normal quando o jogo fechar)."))
        except Exception as exc:
            return ("warn", tr('Plano de energia não alterado: {}').format(exc))

    def boost_gpu(self):
        """GPU de alto desempenho para o jogo (Roblox pega também versões novas). (nível, texto) ou None."""
        if not self.gpu_pref:
            return None
        try:
            paths = gpu_targets_for(self.game, self._settings_ref)
            if not paths:
                return None
            changed = gpu_pref_apply(paths)
        except Exception as exc:
            return ("warn", tr('Preferência de GPU não alterada: {}').format(exc))
        if not changed:
            return None
        owned = set(self._settings_ref.get("gpu_paths", [])) | set(changed)
        self._settings_ref["gpu_paths"] = sorted(owned)
        return ("ok", tr('{}: GPU de alto desempenho para {} instalação(ões). Vale na próxima vez que o jogo abrir.').format(game_title(self.game), len(changed)))

    def restore_power(self):
        if self.power_prev:
            if set_power_scheme(self.power_prev):
                clear_power_state()
            self.power_prev = None

    # ---- restaurar ---------------------------------------------------

    def restore(self):
        """Devolve cada processo ao estado original (só se ainda for o mesmo programa)."""
        current = list_processes()
        restored = failed = 0
        for pid, info in list(self.saved.items()):
            if current.get(pid) != info["name"]:
                continue  # fechou ou o PID foi reutilizado: não mexe
            if restore_process(pid, info):
                restored += 1
            else:
                failed += 1
        self.saved.clear()
        self.done.clear()
        self.apps.clear()
        self.in_use.clear()
        self.total_freed = 0
        self.game_ok = False
        try:
            self.restore_power()
        except Exception:
            pass
        return restored, failed


def human_size(n):
    mb = n / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def report_lines(rep):
    """Transforma um Report em linhas [(nível, texto)] para o painel de avisos."""
    lines = []
    for ok, text in rep.game:
        if ok:
            lines.append(("ok", tr('Jogo: {}').format(text)))
        else:
            lines.append(("warn", tr('Jogo: {}').format(text)))
            if tr("acesso negado") in text:
                lines.append(("info", tr("O jogo parece protegido (anti-cheat). Os apps em segundo "
                                      "plano ainda serão acalmados e a memória liberada.")))
    if rep.calmed:
        total = sum(rep.calmed.values())
        lines.append(("ok", tr('{} processo(s) em segundo plano ficaram mais lentos.').format(total)))
    for why, names in rep.eco_fail.items():
        lines.append(("warn", tr('Modo de eficiência falhou — {}: {}').format(why, ', '.join(sorted(names)[:5]))))
    for why, names in rep.mem_fail.items():
        lines.append(("warn", tr('Prioridade de memória falhou — {}: {}').format(why, ', '.join(sorted(names)[:5]))))
    for why, names in rep.calm_fail.items():
        lines.append(("warn", tr('Não consegui desacelerar — {}: {}').format(why, ', '.join(sorted(names)[:5]))))
    if rep.trim_ok:
        lines.append(("ok", tr('Memória liberada: {} em {} processo(s).').format(human_size(rep.freed), rep.trim_ok)))
    if rep.skipped:
        lines.append(("info", tr('{} processo(s) do sistema ignorados (o Windows não deixa mexer).').format(rep.skipped)))
    return lines


# --------------------------------------------------------------------------
# Motor (roda em segundo plano, fora da interface)
# --------------------------------------------------------------------------

EMPTY_SNAPSHOT = {"running": False, "boosted": False, "slowed": 0, "procs": 0,
                  "touched": 0, "freed": 0, "rows": [], "since": 0.0}


def set_awake(on):
    """Enquanto ligado, o Windows não apaga a tela nem dorme. Some sozinho se o programa fechar."""
    try:
        fn = kernel32.SetThreadExecutionState
        fn.argtypes = [wintypes.DWORD]
        fn.restype = wintypes.DWORD
        fn(0x80000000 | (0x00000001 | 0x00000002 if on else 0))   # CONTINUOUS (+ SYSTEM + DISPLAY)
    except Exception:
        pass


class Engine(threading.Thread):
    def __init__(self, settings, events):
        super().__init__(daemon=True)
        self.settings = settings
        self.events = events
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._snap = EMPTY_SNAPSHOT
        self._since = 0.0
        self._session_sig = None

    def stop(self):
        self.stop_event.set()

    def snapshot(self):
        with self._lock:
            return self._snap

    def log(self, level, text):
        self.events.put((level, text))

    def _publish(self, mode, running):
        rows = []
        for name, e in mode.apps.items():
            parts = []
            if name in mode.in_use:
                parts.append(tr("em uso agora (normal)"))
            if e["slowed"]:
                parts.append(tr("prioridade baixa"))
                if e["eco"]:
                    parts.append(tr("modo eficiência"))
                if e["mem"]:
                    parts.append(tr("memória baixa"))
                if e.get("io"):
                    parts.append(tr("disco baixo"))
                if e.get("cpu"):
                    parts.append(tr("menos núcleos"))
            if e["freed"]:
                parts.append(tr("memória liberada"))
            rows.append((len(e["slowed"]), e["freed"], name, len(e["pids"]),
                         " + ".join(parts) if parts else "—"))
        rows.sort(key=lambda r: (-r[0], -r[1], r[2]))
        snap = {
            "running": running,
            "boosted": mode.game_ok,
            "slowed": sum(1 for e in mode.apps.values() if e["slowed"]),
            "procs": sum(len(e["slowed"]) for e in mode.apps.values()),
            "touched": sum(len(e["pids"]) for e in mode.apps.values()),
            "freed": mode.total_freed,
            "since": self._since if running else 0.0,
            "rows": [(name, procs, action, human_size(freed) if freed else "—")
                     for _s, freed, name, procs, action in rows],
        }
        with self._lock:
            self._snap = snap

    def _check_focus(self, mode, procs):
        """Libera/volta a desacelerar conforme o app que está em primeiro plano."""
        try:
            fg = foreground_exe()
        except Exception:
            return False
        before = set(mode.in_use)
        changed = mode.set_foreground(fg, procs)
        for name in sorted(mode.in_use - before):
            self.log("info", tr('{} está em uso: voltou ao normal até você sair dele.').format(name))
        for name in sorted(before - mode.in_use):
            self.log("info", tr('Você saiu de {}: ele ficou mais lento de novo.').format(name))
        return changed

    def _sync_session(self, mode):
        """Mantém em arquivo o que foi alterado (só grava quando muda)."""
        try:
            sig = json.dumps(mode.saved, sort_keys=True)
            if sig != self._session_sig:
                self._session_sig = sig
                save_session(mode.saved)
        except Exception:
            pass

    def run(self):
        mode = GameMode(self.settings)
        game = self.settings["game"]
        last_trim = time.time()
        seen_warnings = set()
        last_procs = None
        last_running = None
        idle_since = time.time()
        awake = False
        try:
            while not self.stop_event.is_set():
                procs = list_processes()
                running = any(n == mode.game for n in procs.values())
                dirty = running != last_running
                want_awake = bool(running and self.settings.get("keep_awake", True))
                if want_awake != awake:
                    awake = want_awake
                    set_awake(awake)

                if running:
                    first_pass = not mode.active
                    if first_pass:
                        self.log("info", tr('{} detectado. Aplicando otimizações.').format(game))
                        mode.active = True
                        power = mode.boost_power()
                        if power:
                            self.log(*power)
                        gpu = mode.boost_gpu()
                        if gpu:
                            self.log(*gpu)
                        last_trim = time.time()
                        seen_warnings.clear()
                        last_procs = None
                        self._since = time.time()
                    if procs != last_procs:  # só reprocessa se a lista de programas mudou
                        last_procs = procs
                        dirty = True
                        rep = mode.apply(procs)
                        for level, text in report_lines(rep):
                            if level == "warn":
                                if text in seen_warnings:
                                    continue  # não repete o mesmo aviso
                                seen_warnings.add(text)
                            elif not first_pass:
                                continue  # depois da 1ª passada, só avisos novos
                            self.log(level, text)
                    if (self.settings["trim"] and self.settings["retrim"]
                            and time.time() - last_trim >= RETRIM_SECONDS):
                        last_trim = time.time()
                        freed, count = mode.retrim(procs)
                        if count:
                            dirty = True
                            self.log("ok", tr('Limpeza periódica: mais {} liberados em {} processo(s).').format(human_size(freed), count))
                elif mode.active:
                    self.log("info", tr('{} fechou. Restaurando tudo.').format(game))
                    n, failed = mode.restore()
                    mode.active = False
                    last_procs = None
                    dirty = True
                    self._since = 0.0
                    self.log("info", tr('{} processo(s) restaurado(s)').format(n)
                             + (tr(', {} não deixaram restaurar.').format(failed) if failed else "."))

                if dirty:
                    self._publish(mode, running)
                    self._sync_session(mode)
                last_running = running
                if running:
                    idle_since = None
                    pause = POLL_ACTIVE_SECONDS * PERF["engine"]
                else:
                    if idle_since is None:
                        idle_since = time.time()
                    waited = time.time() - idle_since
                    pause = (POLL_SECONDS if waited < IDLE_SLOW_AFTER
                             else POLL_IDLE_SLOW_SECONDS) * PERF["engine"]
                if running and self.settings.get("unslow_active", True):
                    end = time.time() + pause
                    while not self.stop_event.is_set():
                        left = end - time.time()
                        if left <= 0:
                            break
                        self.stop_event.wait(min(0.4, left))
                        if mode.active and self._check_focus(mode, procs):
                            self._publish(mode, running)
                            self._sync_session(mode)
                else:
                    self.stop_event.wait(pause)
        except Exception:
            self.log("warn", tr("Erro inesperado no Game Mode:\n") + traceback.format_exc())
        finally:
            set_awake(False)
            n, failed = mode.restore()
            if n or failed:
                self.log("info", tr('{} processo(s) restaurado(s)').format(n)
                         + (tr(', {} não deixaram restaurar.').format(failed) if failed else "."))
            self._since = 0.0
            self._publish(mode, False)
            self._sync_session(mode)  # sessão encerrada direito: apaga o arquivo


# --------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------

_PAL = gm_i18n.palette() if gm_i18n is not None else {}
_DARK_UI = (gm_i18n.theme() if gm_i18n is not None else "dark") != "light"


def _pal(name, fallback):
    return _PAL.get(name, fallback)


BG = _pal("BG", "#14151a")
SIDE = _pal("SIDE", "#191b21")
CARD = _pal("CARD", "#1b1d24")
PANEL = _pal("PANEL", "#23262e")
BORDER = _pal("BORDER", "#2a2d36")
TEXT = _pal("TEXT", "#e8eaf0")
MUTED = _pal("MUTED", "#8b909c")
ACCENT = _pal("ACCENT", "#4f8cff")
GREEN = _pal("GREEN", "#35d07f")
WARN = _pal("WARN", "#f5a623")
PINK = _pal("PINK", "#c678dd")
TEAL = _pal("TEAL", "#2ec4b6")
SEL = _pal("SEL", "#22304f")                    # selected row
ACCENT_HOVER = _pal("ACCENT_HOVER", "#3d78e6")
OFF = _pal("OFF", "#3a3d47")
OFF_DIS = _pal("OFF_DIS", "#2c2e36")
KNOB_DIS = _pal("KNOB_DIS", "#6b6f7a")
ICON = _pal("ICON", "#9aa0ab")
ICON_HOVER = _pal("ICON_HOVER", "#c5c9d3")
ICON_BG = _pal("ICON_BG", "#1f2a44")
BTN_BG = _pal("BTN_BG", "#12131a")
GLOW1 = _pal("GLOW1", "#172340")
GLOW2 = _pal("GLOW2", "#1a2a4d")
GLOW3 = _pal("GLOW3", "#203764")

FONT = "Segoe UI"

LEVEL_COLOR = {"ok": GREEN, "warn": WARN, "info": MUTED}

QOS_LABELS = [("high", tr("Alta (46)")), ("video", tr("Vídeo (34)")), ("low", tr("Baixa (8)")),
              ("custom", tr("Personalizado"))]
MOVE_LABELS = [("neutral", tr("Neutro")), ("first", tr("Primeira tecla")), ("last", tr("Última tecla"))]
QOS_VALUES = {"high": 46, "video": 34, "low": 8}


def label_of(pairs, key):
    for k, label in pairs:
        if k == key:
            return label
    return pairs[0][1]


def key_of(pairs, label):
    for k, text in pairs:
        if text == label:
            return k
    return pairs[0][0]


def game_title(game):
    if "funkin" in game.lower():
        return "Friday Night Funkin'"
    if game.lower() == "javaw.exe":
        return "Minecraft"
    if game.lower() == "minecraft.windows.exe":
        return "Minecraft Bedrock"
    if "roblox" in game.lower():
        return "Roblox"
    return game.rsplit(".", 1)[0].title()


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def normalize_app_name(text):
    """'Chrome', ' C:\\x\\chrome.EXE ' -> 'chrome.exe'. Vazio se não sobrar nada."""
    name = text.strip().strip('"').strip("'").strip()
    name = name.replace("/", "\\").rsplit("\\", 1)[-1].strip().lower()
    if not name:
        return ""
    if name in ("system", "registry") or name.endswith(".exe"):
        return name
    return name + ".exe"


class AppListEditor(tk.Frame):
    """Lista de programas com Adicionar / Remover (no lugar de editar texto)."""

    def __init__(self, parent, title, items, choices_fn, blocked_fn=None, height=7, hint=""):
        super().__init__(parent, bg=BG)
        self.choices_fn = choices_fn
        self.blocked_fn = blocked_fn
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", pady=(0, 4))
        tk.Label(head, text=title, bg=BG, fg=TEXT, font=(FONT, 9, "bold")).pack(side="left")
        self.count = tk.Label(head, bg=BG, fg=MUTED, font=(FONT, 9))
        self.count.pack(side="right")
        if hint:
            tk.Label(self, text=hint, bg=BG, fg=MUTED, font=(FONT, 8), wraplength=480,
                     justify="left").pack(anchor="w", pady=(0, 4))
        box = tk.Frame(self, bg=PANEL)
        box.pack(fill="x")
        self.listbox = tk.Listbox(
            box, height=height, selectmode="extended", bg=PANEL, fg=TEXT,
            selectbackground=ACCENT, selectforeground="#ffffff", relief="flat", bd=0,
            highlightthickness=0, font=("Consolas", 10), activestyle="none",
            exportselection=False)
        bar = ttk.Scrollbar(box, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=bar.set)
        self.listbox.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=4)
        bar.pack(side="right", fill="y")
        self.listbox.bind("<Delete>", lambda _e: self.remove())

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", pady=(8, 0))
        self.var = tk.StringVar()
        self.combo = ttk.Combobox(row, textvariable=self.var, font=(FONT, 9))
        self.combo.pack(side="left", fill="x", expand=True, ipady=2)
        self.combo.bind("<Return>", lambda _e: self.add())
        self._button(row, tr("Adicionar"), self.add, ACCENT, "#ffffff").pack(side="left", padx=(8, 0))
        self._button(row, tr("Remover selecionados"), self.remove, PANEL, TEXT).pack(
            side="left", padx=(8, 0))
        self._button(row, "\u21BB", self.refresh_choices, PANEL, TEXT, padx=9).pack(
            side="left", padx=(8, 0))
        tk.Label(self, text=tr("Escolha um programa aberto na caixa ou digite o nome (ex.: chrome)."),
                 bg=BG, fg=MUTED, font=(FONT, 8)).pack(anchor="w", pady=(4, 0))
        self.set(items)
        self.refresh_choices()

    @staticmethod
    def _button(parent, text, command, bg, fg, padx=12):
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0,
                         padx=padx, pady=5, font=(FONT, 9), cursor="hand2")

    def get(self):
        return sorted(set(self.listbox.get(0, "end")))

    def set(self, items):
        self.listbox.delete(0, "end")
        for name in sorted({normalize_app_name(i) for i in items if normalize_app_name(i)}):
            self.listbox.insert("end", name)
        self._update_count()

    def _update_count(self):
        self.count.config(text=f"{self.listbox.size()} apps")

    def refresh_choices(self):
        try:
            have = set(self.listbox.get(0, "end"))
            self.combo.config(values=[n for n in self.choices_fn() if n not in have])
        except Exception:
            self.combo.config(values=[])

    def add(self):
        name = normalize_app_name(self.var.get())
        if not name:
            return
        if name in self.listbox.get(0, "end"):
            self.var.set("")
            return
        if self.blocked_fn is not None:
            msg = self.blocked_fn(name)
            if msg:
                messagebox.showwarning("Apps", msg, parent=self.winfo_toplevel())
                return
        names = sorted(set(self.listbox.get(0, "end")) | {name})
        self.set(names)
        self.listbox.see(names.index(name))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(names.index(name))
        self.var.set("")
        self.refresh_choices()

    def remove(self):
        picked = list(self.listbox.curselection())
        for index in reversed(picked):
            self.listbox.delete(index)
        self._update_count()
        self.refresh_choices()


class Switch(tk.Canvas):
    """Interruptor liga/desliga."""

    def __init__(self, parent, bg=CARD, value=False, command=None):
        super().__init__(parent, width=44, height=24, bg=bg, highlightthickness=0, cursor="hand2")
        self.value = bool(value)
        self.command = command
        self.enabled = True
        self.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, _event):
        if not self.enabled:
            return
        self.set(not self.value)
        if self.command:
            self.command(self.value)

    def set(self, value):
        self.value = bool(value)
        self._draw()

    def get(self):
        return self.value

    def lock(self, locked):
        self.enabled = not locked
        self._draw()

    def _draw(self):
        self.delete("all")
        color = (ACCENT if self.value else OFF) if self.enabled else OFF_DIS
        rounded_rect(self, 2, 2, 42, 22, 10, fill=color, outline="")
        x = 24 if self.value else 4
        self.create_oval(x, 5, x + 16, 21, fill="#ffffff" if self.enabled else KNOB_DIS, outline="")


class ScrollFrame(tk.Frame):
    """Área com barra de rolagem (e roda do mouse)."""

    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        self.inner.bind("<Configure>",
                        lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event):
        """Rola só se o mouse estiver sobre esta área (e ela estiver visível)."""
        try:
            if not self.winfo_ismapped():
                return
            widget = self.winfo_containing(event.x_root, event.y_root)
            while widget is not None and widget is not self:
                widget = getattr(widget, "master", None)
            if widget is self:
                self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass  # a janela que tinha esta área já foi fechada


class App:
    def __init__(self, root, start_minimized=False):
        self.root = root
        self.settings = load_settings()
        set_perf(self.settings["perf"].get("level", "normal"))
        self._names_cache = (0.0, set())    # programas abertos (nome, quando)
        self._gt_at = 0.0                   # última vez que olhei o jogo/perfil
        self._path_at = 0.0                 # última tentativa de achar o caminho do jogo
        self.log_lines = deque(maxlen=300)  # para "Copiar avisos" e o diagnóstico
        self._rb_cache = (0.0, False)       # (quando, Roblox aberto?)
        self.events = queue.Queue()        # avisos (qualquer thread -> painel de avisos)
        self.after_queue = queue.Queue()   # tarefas para rodar na thread da janela
        self.engine = None
        self.stopping = False
        self.pending_restart = False
        self.last_live = None
        self.tab = "game"
        self.move = None                   # MovementHelper ligado
        self._last_rows = None
        self._drawn = None
        self._cfg_cache = {}
        self._last_snap = None
        self._last_key = None
        self._minimized = False
        self._low_power = None
        self._last_error = None
        self.hover = False
        self._bright_current = 100          # brilho que está na tela agora
        self._bright_method = "normal"      # como foi aplicado: gamma | mag | overlay | normal
        self._bright_test = False           # teste de brilho aberto: pausa o ajuste normal
        self.overlay = DimOverlay(root)
        self._bright_job = None
        self._bright_key_down = False
        self._bright_n = 0
        self._shader_key = None
        self._shader_job = None
        self._shader_loading = False
        self._shader_buttons = {}
        self.hud_stats = StatsReader()
        self.hud_input = InputWatcher()
        self.hud = HudOverlay(root, self.settings, self.hud_stats, self.hud_input)
        self.hud.session_fn = lambda: self._pt_session
        self.hud_stats.set_host(self.settings["overlay"]["ping_host"])
        self._hud_n = 0
        self._fg_cache = (0.0, False)
        self._flash_dim = 0.0               # quanto o flash está escurecendo agora (pontos de %)
        self._flash_active = False          # medindo a imagem do jogo agora
        self._auto_luma = 0.0               # claridade da cena
        self._auto_brain = FlashGuard()
        self._auto_ok = True
        self._auto_stop = threading.Event()
        self._mods_ok = False               # aba Mods montada sem erro
        self._apps_win = None
        self._pt = gm_extras.load_playtime(PLAYTIME_PATH) if gm_extras else None
        self._pt_last = None                # última medição do tempo de jogo
        self._pt_session = 0.0              # segundos da sessão atual
        self._pt_next_break = None          # quando avisar a próxima pausa
        self._pt_saved_at = 0.0
        self._clean_scan = None             # o que a limpeza achou (esperando "Apagar")
        self._hk_prev = {"toggle": False, "reset": False, "gamemode": False, "move": False}
        self._ping_at, self._ping_busy, self._ping_last = 0.0, False, None   # aviso de ping alto
        self._ping_new, self._ping_bad, self._ping_alert_at = False, 0, 0.0
        self._ensure_profiles()
        self._boot_at = time.time()
        self._upd_busy, self._upd_installing = False, False       # atualização automática
        self._upd_result, self._upd_ready, self._upd_status = None, None, None
        self._upd_notified = set()
        self._fnf_warned = False

        root.title("Game Mode")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h, x, y = fit_geometry(self.settings["window"], sw, sh)
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(min(960, w), min(680, h))
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Unmap>", self._on_unmap)
        root.bind("<Map>", self._on_map)
        self._dark_titlebar()
        self._styles()
        self._build()
        self.draw_power()
        self._tune()
        self.refresh()
        if start_minimized or self.settings["start_minimized"]:
            root.after(150, root.iconify)
        else:
            self._bring_to_front()
        if gm_mods is not None and self.settings["window"].get("tab") == "mods":
            self.select_tab("mods")
        elif self.settings["window"].get("tab") == "display":
            self.select_tab("mods")
        threading.Thread(target=self._auto_worker, daemon=True).start()
        root.after(900, self._hud_tick)
        root.after(1000, self._hotkey_tick)
        root.after(2500, self._apply_gpu_pref)
        root.after(700, self._bright_tick)
        root.after(300, self._startup_actions)
        root.after(1500, trim_self)  # devolve a memória usada para montar a janela
        root.after(2500, lambda: (gc.collect(), gc.freeze()))

    def _bring_to_front(self):
        """Garante que a janela não abra escondida atrás de outras."""
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(400, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    # ---- aparência ---------------------------------------------------

    def _dark_titlebar(self):
        try:
            self.root.update()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(1 if _DARK_UI else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    def _styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                        borderwidth=0, rowheight=28, font=(FONT, 10))
        style.configure("Treeview.Heading", background=PANEL, foreground=MUTED, relief="flat",
                        borderwidth=0, font=(FONT, 9, "bold"))
        style.map("Treeview", background=[("selected", SEL)],
                  foreground=[("selected", TEXT)])
        style.map("Treeview.Heading", background=[("active", PANEL)])
        style.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=TEXT,
                        arrowcolor=MUTED, bordercolor=BORDER, lightcolor=PANEL, darkcolor=PANEL,
                        selectbackground=PANEL, selectforeground=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL), ("disabled", BG)],
                  foreground=[("readonly", TEXT), ("disabled", MUTED)],
                  selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", TEXT)])
        for opt, val in (("background", PANEL), ("foreground", TEXT),
                         ("selectBackground", ACCENT), ("selectForeground", "#ffffff")):
            self.root.option_add("*TCombobox*Listbox." + opt, val)

    # ---- montagem da janela -----------------------------------------

    def _build(self):
        root = self.root
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        header = tk.Frame(root, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(16, 12))
        tk.Label(header, text="\U0001F3AE", bg=ICON_BG, fg=ACCENT,
                 font=("Segoe UI Emoji", 14), width=3).pack(side="left")
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="Game Mode", bg=BG, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(titles, text=tr("Ligue e jogue. O resto é automático."), bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w")

        tabs = tk.Frame(header, bg=BG)
        tabs.pack(side="left", padx=(26, 0))
        self.tab_btn = {}
        for key, text in (("game", "Game Mode"), ("mods", "Mods")):
            b = tk.Label(tabs, text=text, bg=BG, fg=MUTED, font=(FONT, 10, "bold"),
                         padx=16, pady=7, cursor="hand2")
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda _e, k=key: self.select_tab(k))
            self.tab_btn[key] = b

        tk.Button(header, text=tr("\u2699  Opções"), command=self.open_options, bg=PANEL, fg=TEXT,
                  activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0,
                  padx=14, pady=6, font=(FONT, 9), cursor="hand2").pack(side="right")
        self.chip = tk.Label(header, bg=PANEL, fg=MUTED, font=(FONT, 9), padx=12, pady=6)
        self.chip.pack(side="right", padx=10)

        content = tk.Frame(root, bg=BG)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        self.page_game = tk.Frame(content, bg=BG)
        self.page_mods = tk.Frame(content, bg=BG)
        for page in (self.page_game, self.page_mods):
            page.grid(row=0, column=0, sticky="nsew")
        self._build_game_page(self.page_game)
        self._build_mods_page(self.page_mods)
        self.select_tab("game")

    def select_tab(self, key):
        self.tab = key
        for k, b in self.tab_btn.items():
            b.config(fg=TEXT if k == key else MUTED, bg=PANEL if k == key else BG)
        {"game": self.page_game, "mods": self.page_mods}[key].tkraise()
        if key == "mods":
            try:
                self.refresh_mod_badges()
            except Exception:
                pass  # os selos são só informativos: nunca podem impedir o programa de abrir

    # ---- aba Game Mode ----------------------------------------------

    def _build_game_page(self, page):
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=1)

        side = tk.Frame(page, bg=SIDE, width=300, highlightthickness=1,
                        highlightbackground=BORDER)
        side.grid(row=0, column=0, sticky="ns", padx=(22, 14), pady=(0, 20))
        side.pack_propagate(False)

        self.canvas = tk.Canvas(side, width=260, height=250, bg=SIDE, highlightthickness=0,
                                cursor="hand2")
        self.canvas.pack(pady=(22, 0))
        self.canvas.bind("<Button-1>", lambda _e: self.toggle())
        self.canvas.bind("<Enter>", lambda _e: self._set_hover(True))
        self.canvas.bind("<Leave>", lambda _e: self._set_hover(False))

        self.status = tk.Label(side, bg=SIDE, fg=MUTED, font=(FONT, 10), wraplength=250,
                               justify="center")
        self.status.pack(padx=16, pady=(6, 14))

        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=20)
        tk.Label(side, text=tr("CONFIGURAÇÃO ATUAL"), bg=SIDE, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=20, pady=(14, 6))
        self.info = tk.Label(side, bg=SIDE, fg=TEXT, font=(FONT, 9), justify="left",
                             anchor="w", wraplength=250)
        self.info.pack(fill="x", padx=20)

        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(16, 0))
        self.panic_btn = tk.Button(
            side, text=tr("Restaurar tudo agora"), command=self.panic_restore, bg=PANEL, fg=TEXT,
            activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0, padx=14,
            pady=7, font=(FONT, 9), cursor="hand2")
        self.panic_btn.pack(padx=20, pady=(12, 4), fill="x")
        tk.Label(side, text=tr("Devolve a prioridade e a memória dos apps e solta teclas e cliques."),
                 bg=SIDE, fg=MUTED, font=(FONT, 8), wraplength=250, justify="left").pack(
                     anchor="w", padx=20)

        main = tk.Frame(page, bg=BG)
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 22), pady=(0, 20))
        for col in range(3):
            main.grid_columnconfigure(col, weight=1, uniform="tile")
        main.grid_rowconfigure(2, weight=1)

        self.tile_apps = self._tile(main, 0, tr("APPS DESACELERADOS"), WARN)
        self.tile_mem = self._tile(main, 1, tr("MEMÓRIA LIBERADA"), GREEN)
        self.tile_game = self._tile(main, 2, tr("JOGO"), ACCENT)

        table_head = tk.Frame(main, bg=BG)
        table_head.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(16, 6))
        tk.Label(table_head, text=tr("Apps que foram diminuídos"), bg=BG, fg=TEXT,
                 font=(FONT, 10, "bold")).pack(side="left")
        tk.Button(table_head, text=tr("+ Adicionar / remover apps"), command=self.open_apps_manager,
                  bg=PANEL, fg=TEXT, activebackground=BORDER, activeforeground=TEXT,
                  relief="flat", bd=0, padx=12, pady=4, font=(FONT, 9),
                  cursor="hand2").pack(side="right")
        table = tk.Frame(main, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        table.grid(row=2, column=0, columnspan=3, sticky="nsew")
        cols = ("app", "procs", "acao", "mem")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", height=6)
        for key, text, width, anchor in [
                ("app", "App", 170, "w"), ("procs", tr("Processos"), 80, "center"),
                ("acao", tr("O que foi feito"), 330, "w"), ("mem", tr("Memória liberada"), 120, "e")]:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == "acao"))
        self.tree.tag_configure("slowed", foreground=TEXT)
        self.tree.tag_configure("memonly", foreground=MUTED)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.empty_label = tk.Label(
            table, text=tr("Nada por aqui ainda. Ligue o Game Mode e abra o jogo."),
            bg=CARD, fg=MUTED, font=(FONT, 10))

        logbar = tk.Frame(main, bg=BG)
        logbar.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(14, 6))
        tk.Label(logbar, text=tr("Avisos"), bg=BG, fg=TEXT, font=(FONT, 10, "bold")).pack(side="left")
        for text, command in ((tr("Limpar"), self.clear_log), (tr("Copiar"), self.copy_log)):
            tk.Button(logbar, text=text, command=command, bg=BG, fg=MUTED, activebackground=BG,
                      activeforeground=TEXT, relief="flat", bd=0, padx=8, font=(FONT, 9),
                      cursor="hand2").pack(side="right")
        logframe = tk.Frame(main, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        logframe.grid(row=4, column=0, columnspan=3, sticky="ew")
        self.log = tk.Text(logframe, height=6, bg=CARD, fg=MUTED, bd=0, relief="flat",
                           font=("Consolas", 9), wrap="word", state="disabled",
                           padx=10, pady=8)
        self.log.pack(fill="x")
        self.log.tag_configure("ok", foreground=GREEN)
        self.log.tag_configure("warn", foreground=WARN)
        self.log.tag_configure("info", foreground=MUTED)

    def _tile(self, parent, col, title, accent):
        tile = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        tile.grid(row=0, column=col, sticky="nsew",
                  padx=(0 if col == 0 else 7, 0 if col == 2 else 7))
        tk.Frame(tile, bg=accent, height=3).pack(fill="x")
        tk.Label(tile, text=title, bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).pack(
            anchor="w", padx=16, pady=(12, 0))
        value = tk.Label(tile, text="0", bg=CARD, fg=accent, font=(FONT, 28, "bold"))
        value.pack(anchor="w", padx=16)
        sub = tk.Label(tile, text=" ", bg=CARD, fg=MUTED, font=(FONT, 9))
        sub.pack(anchor="w", padx=16, pady=(0, 14))
        return value, sub, accent

    def _set_tile(self, tile, value, sub, dim=False):
        label, sub_label, accent = tile
        self._cfg(label, text=value, fg=MUTED if dim else accent)
        self._cfg(sub_label, text=sub)

    # ---- aba Mods ----------------------------------------------------

    def _mod_card(self, parent, row, col, title, desc, accent, span=1):
        """Cartão da aba Mods. Retorna (corpo, selo, status, engrenagem): o que fica sempre
        visível vai no corpo; as configurações vão na engrenagem (abre/fecha com o ícone)."""
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        if span == 2:
            card.grid(row=row, column=0, columnspan=2, sticky="nsew", pady=(0, 14))
        else:
            card.grid(row=row, column=col, sticky="nsew", pady=(0, 14),
                      padx=(0, 8) if col == 0 else (8, 0))
        tk.Frame(card, bg=accent, height=3).pack(fill="x")
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(head, text=title, bg=CARD, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left")
        gear_btn = tk.Button(head, text="\u2699", bg=CARD, fg=MUTED, activebackground=CARD,
                             activeforeground=TEXT, relief="flat", bd=0, padx=6, pady=0,
                             font=("Segoe UI Symbol", 13), cursor="hand2")
        gear_btn.pack(side="right")
        badge = tk.Label(head, text="", bg=CARD, fg=MUTED, font=(FONT, 9, "bold"))
        badge.pack(side="right", padx=(0, 4))
        tk.Label(card, text=desc, bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=900 if span == 2 else 430, justify="left").pack(
                     anchor="w", padx=16, pady=(4, 8))
        body = tk.Frame(card, bg=CARD)
        body.pack(fill="x", padx=16)
        status = tk.Label(card, text="", bg=CARD, fg=MUTED, font=(FONT, 9),
                          wraplength=900 if span == 2 else 430, justify="left", anchor="w")
        status.pack(fill="x", padx=16, pady=(8, 14))
        settings = tk.Frame(card, bg=CARD)
        state = {"open": False}

        def toggle():
            if state["open"]:
                settings.pack_forget()
                gear_btn.config(fg=MUTED)
            else:
                settings.pack(fill="x", padx=16, pady=(10, 0), before=status)
                gear_btn.config(fg=ACCENT)
            state["open"] = not state["open"]

        gear_btn.config(command=toggle)
        return body, badge, status, settings

    def _field(self, body, row, text, widget):
        tk.Label(body, text=text, bg=CARD, fg=TEXT, font=(FONT, 9)).grid(
            row=row, column=0, sticky="w", pady=4, padx=(0, 14))
        widget.grid(row=row, column=1, sticky="w", pady=4)

    def _combo(self, parent, var, values, width=22, readonly=True):
        box = ttk.Combobox(parent, textvariable=var, values=values, width=width,
                           state="readonly" if readonly else "normal", font=(FONT, 9))
        box.bind("<MouseWheel>", self._combo_wheel)
        return box

    def _combo_wheel(self, event):
        """A roda do mouse sobre uma caixa de seleção rola a página (não troca o valor)."""
        scroller = getattr(self, "mods_scroll", None)
        if scroller is not None:
            scroller._wheel(event)
        return "break"

    def _entry(self, parent, var, width=4):
        return tk.Entry(parent, textvariable=var, width=width, bg=PANEL, fg=TEXT,
                        insertbackground=TEXT, relief="flat", font=(FONT, 10), justify="center")

    def _btn(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else PANEL,
                         fg="white" if primary else TEXT, activebackground=ACCENT_HOVER if primary else BORDER,
                         activeforeground="white" if primary else TEXT, relief="flat", bd=0,
                         padx=16, pady=7, font=(FONT, 9, "bold" if primary else "normal"),
                         cursor="hand2")

    def _switch_row(self, body, row, text, value, command=None):
        tk.Label(body, text=text, bg=CARD, fg=TEXT, font=(FONT, 9), wraplength=250,
                 justify="left").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
        sw = Switch(body, CARD, value, command)
        sw.grid(row=row, column=1, sticky="w", pady=4)
        return sw

    def _build_mods_page(self, page):
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        try:
            scroll = ScrollFrame(page, BG)
            self.mods_scroll = scroll
            scroll.grid(row=0, column=0, sticky="nsew", padx=(22, 12), pady=(0, 10))
            inner = scroll.inner
            inner.grid_columnconfigure(0, weight=1, uniform="mods")
            inner.grid_columnconfigure(1, weight=1, uniform="mods")
            mods = self.settings["mods"]
            self._build_qos_card(inner, mods["qos"])
            if gm_mods is not None:
                self._build_move_card(inner, mods["move"])
            else:
                self._build_move_missing(inner)
            self._build_brightness_card(inner)
            self._build_shader_card(inner)
            self._build_overlay_card(inner)
            self._build_wintweaks_card(inner)
            if gm_extras is not None:
                self._build_extra_cards(inner)
            self._mods_ok = True
            return
        except Exception:
            error = traceback.format_exc()
            for child in page.winfo_children():
                child.destroy()
        write_error_log(tr("Mods não carregaram:\n") + error)
        tk.Label(page, text=tr("A aba Mods não pôde carregar. O Game Mode funciona normalmente.\n\n")
                            + error.strip()[-900:], bg=BG, fg=WARN, font=(FONT, 10),
                 justify="left", wraplength=820).place(relx=0.5, rely=0.3, anchor="n")

    def _build_move_missing(self, parent):
        body, _badge, status, _gear = self._mod_card(
            parent, 0, 1, "Movement Helper",
            tr("Indisponível: não achei o arquivo gm_mods.py ao lado do programa. "
            "Coloque ele na mesma pasta e abra de novo."), PINK)
        status.config(text=tr("O QoS ao lado funciona sem esse arquivo."))

    # -- QoS
    def _build_qos_card(self, parent, cfg):
        body, self.qos_badge, self.qos_status, gear = self._mod_card(
            parent, 0, 0, tr("QoS (prioridade de rede)"),
            tr("Marca o tráfego do jogo como importante. Só ajuda se o seu roteador respeitar "
            "essas marcas, e muitos roteadores de casa não respeitam, então não promete ping "
            "menor. O Windows vai pedir permissão de administrador (sem abrir janela de cmd)."),
            TEAL)
        self.v_qos_preset = tk.StringVar(value=label_of(QOS_LABELS, cfg["preset"]))
        self.v_qos_dscp = tk.StringVar(value=str(cfg["dscp"]))
        combo = self._combo(gear, self.v_qos_preset, [t for _, t in QOS_LABELS])
        combo.bind("<<ComboboxSelected>>", lambda _e: self._qos_preset_changed())
        self._field(gear, 0, tr("Prioridade"), combo)
        self._field(gear, 1, tr("Valor DSCP (0 a 63)"), self._entry(gear, self.v_qos_dscp, 5))
        self.sw_qos_all = self._switch_row(
            gear, 2, tr("Valer também em Wi-Fi e Ethernet de casa"), cfg["all_networks"])
        tk.Label(gear, text=tr("Sem isso, o Windows só usa a marca em redes de empresa."),
                 bg=CARD, fg=MUTED, font=(FONT, 8)).grid(row=3, column=0, columnspan=2, sticky="w")
        buttons = tk.Frame(body, bg=CARD)
        buttons.grid(row=0, column=0, sticky="w")
        self.qos_buttons = [self._btn(buttons, tr("Aplicar"), self.qos_apply_click, True),
                            self._btn(buttons, tr("Remover"), self.qos_remove_click)]
        self.qos_buttons[0].pack(side="left")
        self.qos_buttons[1].pack(side="left", padx=8)

    def _qos_preset_changed(self):
        key = key_of(QOS_LABELS, self.v_qos_preset.get())
        if key in QOS_VALUES:
            self.v_qos_dscp.set(str(QOS_VALUES[key]))

    # -- Movement Helper
    def _build_move_card(self, parent, cfg):
        body, self.move_badge, self.move_status, gear = self._mod_card(
            parent, 0, 1, "Movement Helper",
            tr("O que acontece quando você segura duas teclas opostas juntas (esquerda e direita, "
            "ou frente e trás). Só mexe nessas quatro teclas, só com o jogo em foco, e não "
            "grava nada do que você digita."), PINK)
        self.v_move_mode = tk.StringVar(value=label_of(MOVE_LABELS, cfg["mode"]))
        self.move_widgets = []
        combo = self._combo(gear, self.v_move_mode, [t for _, t in MOVE_LABELS])
        self._field(gear, 0, tr("Quando as duas estão apertadas"), combo)
        self.move_widgets.append(combo)
        keys = tk.Frame(gear, bg=CARD)
        self.v_move = {}
        for i, (name, text) in enumerate((("fwd", tr("Frente")), ("back", tr("Trás")),
                                          ("left", tr("Esquerda")), ("right", tr("Direita")))):
            self.v_move[name] = tk.StringVar(value=cfg[name])
            tk.Label(keys, text=text, bg=CARD, fg=MUTED, font=(FONT, 8)).grid(row=0, column=i, padx=4)
            entry = self._entry(keys, self.v_move[name])
            entry.grid(row=1, column=i, padx=4)
            self.move_widgets.append(entry)
        self._field(gear, 1, tr("Teclas"), keys)
        self.sw_move_game = self._switch_row(gear, 2, tr("Só funciona com o jogo em foco"),
                                             cfg["only_game"])
        tk.Label(gear, text=tr("Alguns jogos não permitem este tipo de ferramenta. Confira as "
                            "regras antes de usar online."), bg=CARD, fg=WARN, font=(FONT, 8),
                 wraplength=430, justify="left").grid(row=3, column=0, columnspan=2,
                                                      sticky="w", pady=(6, 0))
        self.sw_move = self._switch_row(body, 0, tr("Ligar o Movement Helper"), False,
                                        self.move_toggle)

    # ---- utilidades dos mods ----------------------------------------

    def notify(self, level, text):
        """Pode ser chamado de qualquer thread."""
        self.events.put((level, text))

    def _status(self, label, level, text):
        self._cfg(label, text=text, fg=LEVEL_COLOR.get(level, MUTED))

    def _busy(self, buttons, busy):
        for b in buttons:
            b.config(state="disabled" if busy else "normal")

    def _run_bg(self, work, done):
        def runner():
            try:
                result = work()
            except Exception as exc:  # nunca deixa a thread morrer calada
                result = (False, [("warn", tr('Erro inesperado: {}').format(exc))])
            self.after_queue.put(lambda: done(result))
        threading.Thread(target=runner, daemon=True).start()

    def _show_result(self, label, result, buttons=None, after=None):
        ok, msgs = result
        if buttons:
            self._busy(buttons, False)
        worst = "ok" if ok else "warn"
        for level, text in msgs:
            self.add_log(level, text)
            if level == "warn":
                worst = "warn"
        self._status(label, worst, "\n".join(t for _l, t in msgs))
        if after:
            after()

    def _running_names(self, max_age=2.5):
        when, names = self._names_cache
        if time.time() - when > max_age:
            names = set(list_processes().values())
            self._names_cache = (time.time(), names)
        return names

    def _roblox_running(self):
        return self.settings["game"].lower() in self._running_names()   # o jogo escolhido

    # ---- perfis de jogo ------------------------------------------------

    def _ensure_profiles(self):
        """Garante a lista de perfis e que o jogo atual tem um (com o que já estava configurado)."""
        if gm_extras is None:
            return
        s, ov = self.settings, self.settings["overlay"]
        profiles = gm_extras.clean_profiles(s.get("profiles"), valid_looks=set(HUD_LOOKS))
        if not profiles:
            profiles = gm_extras.clean_profiles(DEFAULT_SETTINGS["profiles"], set(HUD_LOOKS))
        if s["profiles_v"] < 2:                      # versão nova: traz os perfis do Minecraft uma vez
            for default in DEFAULT_SETTINGS["profiles"]:
                if (default["exe"].lower() in ("javaw.exe", "minecraft.windows.exe")
                        and gm_extras.find_profile(profiles, default["exe"]) is None):
                    profiles.append(dict(default))
            s["profiles_v"] = 2
        prof = gm_extras.find_profile(profiles, s["game"])
        if prof is None:
            prof = gm_extras.new_profile(s["game"], game_title(s["game"]), ov["ping_host"],
                                         s["gpu_pref"], ov["look"] if ov["look"] in HUD_LOOKS else "Classic")
            profiles.append(prof)
        else:                                # o que está configurado agora vale para o jogo atual
            prof["ping_host"] = ov["ping_host"]
            if ov["look"] in HUD_LOOKS:
                prof["look"] = ov["look"]
            prof["gpu"] = bool(prof["gpu"] or s["gpu_pref"])
        s["gpu_pref"] = prof["gpu"]
        s["profiles"] = profiles

    def _profile_for_game(self):
        if gm_extras is None:
            return None
        return gm_extras.find_profile(self.settings.get("profiles", []), self.settings["game"])

    def _apply_profile_fields(self, prof):
        """Passa o perfil para as configurações (jogo, ping, visual do overlay, GPU)."""
        s, ov = self.settings, self.settings["overlay"]
        s["game"] = prof["exe"]
        s["gpu_pref"] = bool(prof["gpu"])
        ov["ping_host"] = prof["ping_host"]
        try:
            self.hud_stats.set_host(prof["ping_host"])
            if hasattr(self, "v_ping_host"):
                self.v_ping_host.set(prof["ping_host"])
        except Exception:
            pass
        look = prof["look"]
        if look in HUD_LOOKS and ov["look"] != look:    # só mexe se o visual mudou de verdade
            ov["look"] = look
            for key, value in HUD_LOOKS[look][1].items():
                ov["show"][key] = value
                sw = getattr(self, "_hud_switches", {}).get(key)
                if sw is not None:
                    sw.set(value)
            if hasattr(self, "_look_buttons"):
                self._hud_paint_looks()
        self._last_snap = None                          # força a tela principal a redesenhar

    def _switch_game(self, prof):
        self._apply_profile_fields(prof)
        save_settings(self.settings)
        self._apply_gpu_pref()
        if self.move:                                   # o Movement Helper olha o jogo escolhido
            try:
                self.move_toggle(False)
                self.move_toggle(True)
            except Exception:
                pass
        self._restart_engine_if_on()
        self.add_log("info", tr('Jogo trocado para {}.').format(prof['name']))

    def _game_tick(self):
        """Guarda o caminho do jogo e, se ligado, troca sozinho para o jogo da lista que abriu."""
        if gm_extras is None:
            return
        now = time.time()
        if now - self._gt_at < 3.0:
            return
        self._gt_at = now
        s = self.settings
        names = self._running_names()
        cur = s["game"].lower()
        if cur in names:
            prof = self._profile_for_game()
            if prof is not None and not prof.get("path") and now - self._path_at > 30:
                self._path_at = now
                path = process_path_of(cur)
                if path:
                    prof["path"] = path
                    if prof.get("gpu"):
                        self._apply_gpu_pref()
            return
        if s["auto_game"] and not self.stopping and not self.pending_restart:
            target = gm_extras.pick_running(s["profiles"], cur, names)
            if target is not None:
                self._switch_game(target)

    def _roblox_running_cached(self, max_age=3.0):
        when, value = self._rb_cache
        if time.time() - when > max_age:
            value = self._roblox_running()
            self._rb_cache = (time.time(), value)
        return value

    def _collect_mods(self):
        """Lê os campos da aba Mods e guarda nas configurações."""
        if not self._mods_ok:
            return
        m = self.settings["mods"]
        m["qos"]["preset"] = key_of(QOS_LABELS, self.v_qos_preset.get())
        try:
            m["qos"]["dscp"] = int(self.v_qos_dscp.get())
        except ValueError:
            pass
        m["qos"]["all_networks"] = self.sw_qos_all.get()
        if gm_mods is not None and hasattr(self, "v_move_mode"):
            m["move"]["mode"] = key_of(MOVE_LABELS, self.v_move_mode.get())
            for name, var in self.v_move.items():
                if var.get().strip():
                    m["move"][name] = var.get().strip().lower()
            m["move"]["only_game"] = self.sw_move_game.get()

    def _save(self):
        self._collect_mods()
        save_settings(self.settings)

    def refresh_mod_badges(self):
        if not self._mods_ok:
            return
        if hasattr(self, "wt_badge"):
            on = win_tweaks_active()
            self._cfg(self.wt_badge, text=tr("ATIVO") if on else tr("INATIVO"), fg=GREEN if on else MUTED)
        q = qos_status()
        if q.get("active"):
            self._cfg(self.qos_badge, text=tr('ATIVO · DSCP {}').format(q.get('dscp')), fg=GREEN)
        else:
            self._cfg(self.qos_badge, text=tr("INATIVO"), fg=MUTED)

    # -- QoS
    def _qos_parse(self):
        try:
            dscp = int(self.v_qos_dscp.get().strip())
            if not 0 <= dscp <= 63:
                raise ValueError
            return dscp
        except ValueError:
            self._status(self.qos_status, "warn", tr("O valor DSCP precisa ser um número de 0 a 63."))
            return None

    def qos_apply_click(self):
        dscp = self._qos_parse()
        if dscp is None:
            return
        game = self.settings["game"]
        all_net = self.sw_qos_all.get()
        self._save()
        self._busy(self.qos_buttons, True)
        self._status(self.qos_status, "info", tr("Aguardando a permissão de administrador do Windows..."))
        created = []

        def work():
            ok, msgs, nla = qos_apply(game, dscp, all_net)
            created.append(nla)
            return ok, msgs

        def done(result):
            if created and created[0]:
                self.settings["mods"]["qos"]["nla_new"] = True
                save_settings(self.settings)
            self._show_result(self.qos_status, result, self.qos_buttons, self.refresh_mod_badges)

        self._run_bg(work, done)

    def qos_remove_click(self):
        self._busy(self.qos_buttons, True)
        self._status(self.qos_status, "info", tr("Aguardando a permissão de administrador do Windows..."))
        remove_nla = bool(self.settings["mods"]["qos"].get("nla_new"))

        def done(result):
            if result[0]:
                self.settings["mods"]["qos"]["nla_new"] = False
                save_settings(self.settings)
            self._show_result(self.qos_status, result, self.qos_buttons, self.refresh_mod_badges)

        self._run_bg(lambda: qos_remove(remove_nla), done)

    # -- Movement Helper
    def move_toggle(self, on):
        if not on:
            if self.move:
                self.move.stop()
                self.move = None
            for w in self.move_widgets:
                w.config(state="readonly" if isinstance(w, ttk.Combobox) else "normal")
            self.sw_move_game.lock(False)
            self._status(self.move_status, "info", tr("Movement Helper desligado."))
            self._tune()
            return
        keys = {}
        for name, var in self.v_move.items():
            vk = gm_mods.key_to_vk(var.get())
            if vk is None:
                self.sw_move.set(False)
                self._status(self.move_status, "warn",
                             tr("Tecla inválida: '{}'. Use uma letra, número, seta ou F1 a F24.").format(var.get()))
                return
            keys[name] = vk
        mode = key_of(MOVE_LABELS, self.v_move_mode.get())
        try:
            helper = gm_mods.MovementHelper(keys, mode, self.settings["game"],
                                            self.sw_move_game.get(), notify=self.notify)
        except ValueError as exc:
            self.sw_move.set(False)
            self._status(self.move_status, "warn", tr('As quatro teclas precisam ser diferentes ({}).').format(exc))
            return
        ok, msg = helper.start()
        if not ok:
            self.sw_move.set(False)
            self._status(self.move_status, "warn", msg)
            return
        self.move = helper
        for w in self.move_widgets:
            w.config(state="disabled")
        self.sw_move_game.lock(True)
        self._save()
        game = game_title(self.settings["game"])
        self._status(self.move_status, "ok", tr('Ligado. Funciona quando o {} estiver em foco. Desligue para mudar as teclas.').format(game))
        self._tune()

    def _beep(self, high):
        """Bipe curto (em outra thread, para não atrasar nenhum clique)."""
        if not self.settings.get("sounds", True):
            return
        def play():
            try:
                import winsound
                winsound.Beep(1100 if high else 700, 70)
            except Exception:
                pass
        threading.Thread(target=play, daemon=True).start()

    # ---- eficiência do próprio programa -------------------------------

    def _tune(self):
        """Prioridade baixa quando só o Game Mode está ligado; alta quando há entrada em tempo real."""
        low = not (self.move or self._bright_realtime())
        if low != self._low_power:
            self._low_power = low
            try:
                tune_self(low)
            except Exception:
                pass

    def _on_unmap(self, event):
        if event.widget is self.root:
            self._minimized = True
            self.root.after(300, trim_self)

    def _on_map(self, event):
        if event.widget is self.root:
            self._minimized = False

    def _cfg(self, widget, **kw):
        """Só mexe no widget se algo realmente mudou (menos trabalho para a tela)."""
        key = id(widget)
        if self._cfg_cache.get(key) != kw:
            self._cfg_cache[key] = kw
            widget.config(**kw)

    # ---- botão de ligar ---------------------------------------------

    def _set_hover(self, value):
        self.hover = value
        self.draw_power()

    def is_on(self):
        return self.engine is not None and self.engine.is_alive() and not self.stopping

    def draw_power(self):
        on = self.is_on()
        busy = self.stopping
        state = (on, busy, self.hover)
        if state == self._drawn:
            return
        self._drawn = state
        c = self.canvas
        c.delete("all")

        if on:
            for pad, color in ((20, GLOW1), (13, GLOW2), (7, GLOW3)):
                rounded_rect(c, 40 - pad, 20 - pad, 220 + pad, 200 + pad, 40 + pad,
                             outline=color, fill="", width=2)
        ring = ACCENT if on else (OFF if self.hover else BORDER)
        icon = ACCENT if on else (ICON_HOVER if self.hover else ICON)
        rounded_rect(c, 40, 20, 220, 200, 40, outline=ring, fill=BTN_BG, width=3)
        c.create_arc(100, 82, 160, 142, start=125, extent=290, style="arc",
                     outline=icon, width=5)
        c.create_line(130, 74, 130, 112, fill=icon, width=5, capstyle="round")
        label = tr("RESTAURANDO") if busy else (tr("LIGADO") if on else tr("DESLIGADO"))
        c.create_text(130, 228, text=label, fill=ACCENT if on else ICON_HOVER,
                      font=(FONT, 11, "bold"))

    def toggle(self):
        if self.stopping:
            return
        if self.is_on():
            self.engine.stop()
            self.stopping = True
        else:
            self.start_engine()
        self.draw_power()

    def start_engine(self):
        self.engine = Engine(json.loads(json.dumps(self.settings)), self.events)
        self.engine.start()
        self._last_key = None

    # ---- atualização periódica --------------------------------------

    def refresh(self):
        try:
            self._refresh()
        except Exception:
            text = traceback.format_exc()
            if text != self._last_error:  # não repete o mesmo erro
                self._last_error = text
                try:
                    self.add_log("warn", tr("Erro ao atualizar a tela:\n") + text[-600:])
                except Exception:
                    pass
        finally:
            # Janela minimizada: olha só a cada 2 s. Visível: 2 vezes por segundo.
            self.root.after(PERF["minimized"] if self._minimized else 500, self.refresh)

    def _refresh(self):
        try:
            self._playtime_tick()
            self._game_tick()
            self._update_tick()
        except Exception:
            pass
        # Tarefas vindas de outras threads
        try:
            while True:
                self.after_queue.get_nowait()()
        except queue.Empty:
            pass

        # Fim da parada
        if self.stopping and self.engine is not None and not self.engine.is_alive():
            self.engine = None
            self.stopping = False
            self._last_rows = None
            self._last_key = None
            if self.pending_restart:
                self.pending_restart = False
                self.start_engine()

        # Avisos
        try:
            while True:
                level, text = self.events.get_nowait()
                self.add_log(level, text)
        except queue.Empty:
            pass

        if self._minimized:
            return  # sem tela para atualizar

        if self.tab == "mods":
            self._refresh_mod_state()
            self._refresh_extra_state()

        snap = self.engine.snapshot() if self.engine is not None else EMPTY_SNAPSHOT
        on = self.is_on()
        minute = int(time.time() // 60) if (on and snap["running"]) else 0
        key = (on, self.stopping, self.settings["game"], self.settings["eco"],
               self.settings["high"], self.settings["trim"], self.settings["trim_all"], minute)
        if snap is self._last_snap and key == self._last_key:
            self.draw_power()
            return  # nada mudou desde a última vez
        self._last_snap, self._last_key = snap, key

        game = self.settings["game"]
        title = game_title(game)
        live = on and snap["running"]

        if self.stopping:
            status, status_color, chip, chip_color = (
                tr("Restaurando tudo ao normal..."), MUTED, "restaurando", MUTED)
        elif not on:
            status, status_color, chip, chip_color = (
                tr("Game Mode desligado. Tudo está normal."), MUTED, tr('{} · desligado').format(title), MUTED)
        elif not snap["running"]:
            status, status_color, chip, chip_color = (
                tr('Ligado. Começa a funcionar quando o {} abrir.').format(title), ACCENT,
                tr('● {} · aguardando').format(title), ACCENT)
        elif snap["boosted"]:
            status, status_color, chip, chip_color = (
                tr('{} está otimizado.').format(title), GREEN, tr('● {} · otimizado').format(title), GREEN)
        else:
            status, status_color, chip, chip_color = (
                tr('{} está aberto, mas o Windows não permitiu o boost no jogo. Os outros apps foram acalmados.').format(title), WARN, tr('● {} · sem boost').format(title), WARN)
        self._cfg(self.status, text=status, fg=status_color)
        self._cfg(self.chip, text=chip, fg=chip_color)

        eco = "ligado" if self.settings["eco"] else "desligado"
        mem = (tr("todos os apps") if self.settings["trim_all"] else tr("só os da lista")) \
            if self.settings["trim"] else "desligado"
        prio = "alta" if self.settings["high"] else tr("acima do normal")
        self._cfg(self.info, text=tr('Jogo: {}\nPrioridade do jogo: {}\nModo de eficiência: {}\nLiberar memória: {}').format(game, prio, eco, mem))

        if live:
            self.last_live = snap
        shown = snap if live else self.last_live
        dim = not live
        if shown is not None:
            tail = tr("  ·  última sessão") if dim else ""
            self._set_tile(self.tile_apps, str(shown["slowed"]),
                           tr('{} processo(s){}').format(shown['procs'], tail), dim)
            self._set_tile(self.tile_mem, human_size(shown["freed"]),
                           tr('em {} processo(s){}').format(shown['touched'], tail), dim)
        else:
            self._set_tile(self.tile_apps, "0", tr("nenhum ainda"), True)
            self._set_tile(self.tile_mem, "0 MB", tr("nenhuma ainda"), True)

        if not on:
            game_state, game_sub = tr("Desligado"), f"{game}"
        elif not snap["running"]:
            game_state, game_sub = tr("Aguardando"), tr('abra o {}').format(title)
        elif snap["boosted"]:
            game_state = tr("Otimizado")
            game_sub = (tr("há ") + fmt_duration(time.time() - snap["since"])
                        if snap.get("since") else tr("prioridade aplicada"))
        else:
            game_state, game_sub = tr("Sem boost"), tr("o Windows não permitiu")
        self._set_tile(self.tile_game, game_state, game_sub, dim=not on)

        rows = snap["rows"] if live else []
        if rows != self._last_rows:
            self._last_rows = rows
            self.tree.delete(*self.tree.get_children())
            for row in rows:
                tag = "slowed" if tr("prioridade baixa") in row[2] else "memonly"
                self.tree.insert("", "end", values=row, tags=(tag,))
            if rows:
                self.empty_label.place_forget()
            else:
                self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

        self.draw_power()

    def _refresh_mod_state(self):
        """Selo do Movement Helper (só leitura de atributos, é barato)."""
        if gm_mods is None or not self._mods_ok or not hasattr(self, "move_badge"):
            return
        if self.move and self.move.running:
            in_game = bool(self.move.focus and self.move.focus.in_game)
            self._cfg(self.move_badge, text=tr("ATIVO NO JOGO") if in_game else tr("LIGADO · ESPERANDO O JOGO"),
                      fg=GREEN if in_game else ACCENT)
        else:
            self._cfg(self.move_badge, text=tr("DESLIGADO"), fg=MUTED)

    def add_log(self, level, text):
        self.log.config(state="normal")
        stamp = time.strftime("%H:%M:%S")
        self.log_lines.append(f"{stamp}  {text}")
        self.log.insert("end", f"{stamp}  {text}\n", level)
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 300:
            self.log.delete("1.0", f"{lines - 300}.0")
        self.log.see("end")
        self.log.config(state="disabled")

    # ---- opções ------------------------------------------------------

    # ---- ações de qualidade de vida -----------------------------------

    def _startup_actions(self):
        """Roda logo depois que a janela abre: desfaz sessão antiga e liga o Game Mode, se pedido."""
        try:
            done, total = recover_session()
            if total:
                self.add_log("ok" if done else "info",
                             tr('Recuperei {} de {} processo(s) que uma sessão anterior alterou e não chegou a restaurar.').format(done, total))
        except Exception:
            pass
        if self.settings["autostart_mode"] and not self.is_on() and not self.stopping:
            self.toggle()
            self.add_log("info", tr("Game Mode ligado automaticamente ao abrir."))
        try:
            self._after_update_notice()
        except Exception:
            write_error_log("Aviso de atualização falhou:\n" + traceback.format_exc())

    def _after_update_notice(self):
        """Avisa que o programa acabou de ser atualizado (uma vez por versão nova, nunca na 1ª instalação)."""
        current = APP_VERSION.split()[0]
        seen = self.settings.get("seen_version", "")
        if seen == current:
            return
        self.settings["seen_version"] = current
        save_settings(self.settings)
        if _FIRST_RUN or not self.settings.get("update_notice", True):
            return
        self.notify("ok", tr('Game Mode atualizado para a versão {}.').format(current))
        self._beep(True)
        if self._minimized or self.settings["start_minimized"]:
            return                      # janela escondida: fica só o aviso na lista
        win = tk.Toplevel(self.root)
        win.title("Game Mode")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        box = tk.Frame(win, bg=BG)
        box.pack(padx=26, pady=22)
        tk.Label(box, text=tr("Game Mode atualizado!"), bg=BG, fg=TEXT, font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(box, text=tr('Agora você está na versão {}.').format(current), bg=BG, fg=MUTED,
                 font=(FONT, 10)).pack(anchor="w", pady=(4, 10))
        notes = whats_new_text()
        if notes:
            tk.Label(box, text=tr("Novidades"), bg=BG, fg=ACCENT, font=(FONT, 9, "bold")).pack(anchor="w")
            tk.Label(box, text=notes, bg=BG, fg=TEXT, font=(FONT, 9), justify="left",
                     wraplength=400).pack(anchor="w", pady=(4, 0))
        tk.Button(box, text="OK", command=win.destroy, bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
                  activeforeground="white", relief="flat", bd=0, padx=26, pady=7, font=(FONT, 9, "bold"),
                  cursor="hand2").pack(anchor="e", pady=(16, 0))
        win.update_idletasks()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - win.winfo_width()) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - win.winfo_height()) // 3)
        win.geometry(f"+{x}+{y}")
        win.after(400, lambda: win.attributes("-topmost", False))

    def panic_restore(self):
        """Solta tudo: Movement Helper e as mudanças do Game Mode."""
        if gm_mods is not None:
            if self.move:
                self.sw_move.set(False)
                self.move_toggle(False)
        if self.engine is not None and self.engine.is_alive() and not self.stopping:
            self.engine.stop()  # a própria thread do motor restaura tudo ao parar
            self.stopping = True
            self.draw_power()
        try:
            done, total = recover_session()
        except Exception:
            done = total = 0
        extra = tr(' (mais {} de uma sessão anterior)').format(done) if total else ""
        self.add_log("ok", tr("Restaurando tudo agora") + extra + ".")
        self.bright_reset()

    def copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(self.log_lines))

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self.log_lines.clear()

    def diagnostics_text(self):
        """Texto para colar numa conversa de suporte (sem nome de usuário nem caminhos)."""
        try:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        except Exception:
            sw = sh = 0
        s = self.settings
        lines = [
            tr('Game Mode {}').format(APP_VERSION),
            tr('Windows: {}').format(platform.platform()),
            tr('Python: {} ({})').format(sys.version.split()[0], platform.architecture()[0]),
            tr('Tela: {}x{}').format(sw, sh),
            tr('Mods: {}').format(tr('carregados') if gm_mods is not None else tr('indisponíveis')),
            tr('Jogo: {} | Game Mode: {}').format(s['game'], 'ligado' if self.is_on() else 'desligado'),
            tr('Opções: alta={} eficiência={} memória_baixa={} liberar={} todos={} repetir={}').format(s['high'], s['eco'], s['mem_priority'], s['trim'], s['trim_all'], s['retrim']),
            tr('Listas: {} para acalmar, {} protegidos').format(len(s['calm']), len(s['protect'])),
            f"Ligados agora: movement_helper={bool(self.move)}",
            "",
            tr("Configuração dos mods: ") + json.dumps(s["mods"], ensure_ascii=False),
        ]
        if MODS_ERROR:
            lines += ["", tr("Erro ao carregar os mods:"), MODS_ERROR.strip()[-800:]]
        lines += ["", tr("Últimos avisos:")] + list(self.log_lines)[-15:]
        try:
            with open(os.path.join(os.path.dirname(SETTINGS_PATH), "erro.txt"),
                      encoding="utf-8") as f:
                tail = f.read()[-1200:].strip()
            if tail:
                lines += ["", tr("erro.txt (final):"), tail]
        except OSError:
            pass
        return "\n".join(lines)

    def copy_diagnostics(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.diagnostics_text())
        self.add_log("ok", tr("Diagnóstico copiado. É só colar (Ctrl+V) onde quiser."))

    def open_data_folder(self):
        folder = os.path.dirname(SETTINGS_PATH)
        try:
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except (OSError, AttributeError):
            self.add_log("info", tr('Pasta dos dados: {}').format(folder))

    def _program_choices(self):
        """Jogo atual + Roblox + programas abertos agora (para escolher sem digitar)."""
        try:
            names = running_program_names(exclude=set(self.settings["protect"]) | NOT_GAMES)
        except Exception:
            names = []
        first = [self.settings["game"]]
        for extra in [DEFAULT_GAME] + [p["exe"] for p in self.settings.get("profiles", [])]:
            if extra.lower() not in {n.lower() for n in first}:
                first.append(extra)
        seen = {n.lower() for n in first}
        return first + [n for n in names if n.lower() not in seen]

    def _remember_window(self):
        win = self.settings["window"]
        win["tab"] = self.tab
        try:
            if self.root.state() == "normal":  # minimizada: não guarda a posição
                self.root.update_idletasks()
                win.update(w=int(self.root.winfo_width()), h=int(self.root.winfo_height()),
                           x=int(self.root.winfo_x()), y=int(self.root.winfo_y()))
        except Exception:
            pass

    # ---- aba Brilho ---------------------------------------------------

    def _bright_realtime(self):
        d = self.settings["display"]
        sh = self.settings["shader"]
        return bool(d["on"]["flash"] or d["game_boost"] or d["on"]["only_game"]
                    or self._bright_hotkey() != "none" or (sh["on"] and sh["only_game"]))

    def _bright_hotkey(self):
        d = self.settings["display"]
        return d["hotkey"] if d["on"]["hotkey"] else "none"

    # ---- cartão de brilho (dentro da aba Mods) --------------------------

    # ---- esconder / mostrar opções do brilho ---------------------------

    # ---- interruptores reutilizáveis ---------------------------------
    # Qualquer função do brilho pode ter um interruptor (em qualquer lugar da tela).
    # Desligado: a função para de agir e os controles dela ficam apagados até ligar de novo.

    def _fx_switch(self, parent, oid):
        """Cria um interruptor ligado à função `oid`. Vários interruptores da mesma função ficam
        sincronizados."""
        sw = Switch(parent, CARD, self.settings["display"]["on"][oid],
                    lambda value, o=oid: self._fx_set(o, value))
        self._fx.setdefault(oid, {"switches": [], "controls": []})["switches"].append(sw)
        return sw

    def _fx_attach(self, oid, widgets):
        """Liga controles (nome, slider, valor, caixa...) a um interruptor."""
        fx = self._fx.setdefault(oid, {"switches": [], "controls": []})
        on = bool(self.settings["display"]["on"][oid])
        for widget in widgets:
            normal_fg = widget.cget("fg") if isinstance(widget, tk.Label) else None
            fx["controls"].append((widget, normal_fg))
            self._fx_paint(widget, normal_fg, on)

    @staticmethod
    def _fx_paint(widget, normal_fg, on):
        if isinstance(widget, ttk.Combobox):
            widget.config(state="readonly" if on else "disabled")
        elif isinstance(widget, tk.Scale):
            widget.config(state="normal" if on else "disabled")
        elif isinstance(widget, tk.Label):
            widget.config(fg=normal_fg if on else MUTED)

    def _fx_set(self, oid, value):
        value = bool(value)
        self.settings["display"]["on"][oid] = value
        fx = self._fx[oid]
        for sw in fx["switches"]:
            if sw.get() != value:
                sw.set(value)
        for widget, normal_fg in fx["controls"]:
            self._fx_paint(widget, normal_fg, value)
        if oid in ("hotkey", "only_game"):
            self._tune()
        self._bright_kick(0)

    def _flash_preset(self, name):
        for key, value in FLASH_PRESETS[name].items():
            self._auto_scales[key].set(value)

    def _fx_row(self, parent, row, oid, text):
        """Linha 'texto + interruptor' (a tela principal usa isto)."""
        tk.Label(parent, text=text, bg=CARD, fg=TEXT, font=(FONT, 9), wraplength=300,
                 justify="left").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
        sw = self._fx_switch(parent, oid)
        sw.grid(row=row, column=1, sticky="w", pady=4)
        return sw

    def _fx_head(self, parent, row, oid, title):
        """Título de seção da engrenagem com o interruptor da função."""
        box = tk.Frame(parent, bg=CARD)
        box.grid(row=row, column=0, columnspan=3, sticky="w", pady=(12, 2))
        self._fx_switch(box, oid).pack(side="left")
        tk.Label(box, text=title, bg=CARD, fg=WARN, font=(FONT, 9, "bold")).pack(
            side="left", padx=(8, 0))

    def _plain_head(self, parent, row, text):
        tk.Label(parent, text=text, bg=CARD, fg=WARN, font=(FONT, 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(12, 2))

    def _auto_slider(self, parent, row, text, key, lo, hi, unit="%", fx=None, store="display",
                     after=None):
        """Linha com nome, slider e valor; grava direto em settings[store][key]."""
        d = self.settings[store]
        name = tk.Label(parent, text=text, bg=CARD, fg=TEXT, font=(FONT, 9))
        name.grid(row=row, column=0, sticky="w", padx=(0, 14), pady=(4, 0))
        value_label = tk.Label(parent, text=f"{d[key]}{unit}", bg=CARD, fg=ACCENT,
                               font=(FONT, 10, "bold"), width=7)
        value_label.grid(row=row, column=2, padx=(10, 0), pady=(4, 0))

        def changed(raw):
            value = int(float(raw))
            self.settings[store][key] = value
            value_label.config(text=f"{value}{unit}")
            (after or self._bright_kick)()

        scale = tk.Scale(parent, from_=lo, to=hi, orient="horizontal", showvalue=False,
                         length=300, bg=CARD, fg=TEXT, troughcolor=PANEL, highlightthickness=0,
                         bd=0, sliderrelief="flat", activebackground=ACCENT, command=changed)
        scale.grid(row=row, column=1, pady=(4, 0))
        scale.set(max(lo, min(hi, d[key])))
        self._auto_scales[key if store == "display" else f"{store}.{key}"] = scale
        if fx:
            self._fx_attach(fx, [name, scale, value_label])
        return scale

    def _auto_combo(self, parent, row, text, key, labels, cast=str, fx=None, store="display",
                    after=None):
        d = self.settings[store]
        name = tk.Label(parent, text=text, bg=CARD, fg=TEXT, font=(FONT, 9))
        name.grid(row=row, column=0, sticky="w", padx=(0, 14), pady=(6, 0))
        var = tk.StringVar(value=label_of(labels, str(d[key])))
        box = self._combo(parent, var, [t for _k, t in labels], width=18)
        box.grid(row=row, column=1, sticky="w", pady=(6, 0))

        def changed(_event=None):
            self.settings[store][key] = cast(key_of(labels, var.get()))
            if store == "display" and key in ("method", "method_up"):
                self.overlay.hide()  # trocou o jeito de aplicar: limpa e aplica de novo
                restore_brightness()
                self._bright_current = 100
                self._bright_method = "normal"
            (after or (lambda: self._bright_kick(0)))()

        box.bind("<<ComboboxSelected>>", changed)
        if fx:
            self._fx_attach(fx, [name, box])
        return var

    def _build_brightness_card(self, parent):
        d = self.settings["display"]
        self._auto_scales = {}
        self._fx = {}
        body, self.bright_badge, self.bright_status, gear = self._mod_card(
            parent, 1, 0, tr("Brilho da tela"),
            tr("Deixa a tela mais clara (até 200%) para enxergar em áreas escuras. A proteção de "
            "flash escurece a tela na hora quando a imagem do jogo clareia de repente. Cada "
            "função tem um interruptor: desligou, ela para até você ligar de novo. A engrenagem ⚙ "
            "tem os ajustes finos."), WARN, span=2)

        self.bright_value = tk.Label(body, text=f"{d['level']}%", bg=CARD, fg=WARN,
                                     font=(FONT, 20, "bold"))
        self.bright_value.pack(anchor="w")
        self.bright_scale = tk.Scale(
            body, from_=BRIGHT_MIN, to=BRIGHT_MAX, orient="horizontal", showvalue=False,
            length=520, bg=CARD, fg=TEXT, troughcolor=PANEL, highlightthickness=0, bd=0,
            sliderrelief="flat", activebackground=ACCENT, command=self._on_bright_slide)
        self.bright_scale.set(d["level"])
        self.bright_scale.pack(anchor="w")
        presets = tk.Frame(body, bg=CARD)
        presets.pack(anchor="w", pady=(8, 0))
        for text, value in BRIGHT_PRESETS:
            tk.Button(presets, text=f"{text} ({value}%)", bg=PANEL, fg=TEXT,
                      activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0,
                      padx=12, pady=5, font=(FONT, 9), cursor="hand2",
                      command=lambda v=value: self._bright_preset(v)).pack(
                          side="left", padx=(0, 8))
        tk.Button(presets, text=tr("Voltar ao normal"), command=self.bright_reset, bg=PANEL, fg=TEXT,
                  activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0, padx=12,
                  pady=5, font=(FONT, 9), cursor="hand2").pack(side="left", padx=(8, 0))
        tk.Button(presets, text=tr("Testar brilho"), command=self.open_brightness_test, bg=ACCENT,
                  fg="white", activebackground=ACCENT_HOVER, activeforeground="white", relief="flat",
                  bd=0, padx=12, pady=5, font=(FONT, 9, "bold"), cursor="hand2").pack(
                      side="left", padx=(8, 0))

        quick = tk.Frame(body, bg=CARD)
        quick.pack(anchor="w", pady=(10, 0))
        self._fx_row(quick, 0, "only_game", tr("Clarear só dentro do jogo (fora dele a tela fica normal)"))
        self.sw_gboost = self._switch_row(quick, 1, tr("Mais claro dentro do jogo"), d["game_boost"],
                                          self._on_gboost)
        self._fx_row(quick, 2, "flash", tr("Escurecer rápido em flashes"))
        modes = tk.Frame(body, bg=CARD)
        modes.pack(anchor="w", pady=(4, 0))
        tk.Label(modes, text=tr("Proteção de flash:"), bg=CARD, fg=MUTED, font=(FONT, 9)).pack(
            side="left", padx=(0, 8))
        for name in FLASH_PRESETS:
            tk.Button(modes, text=name, bg=PANEL, fg=TEXT, activebackground=BORDER,
                      activeforeground=TEXT, relief="flat", bd=0, padx=12, pady=4,
                      font=(FONT, 9), cursor="hand2",
                      command=lambda n=name: self._flash_preset(n)).pack(side="left", padx=(0, 6))
        self.auto_info = tk.Label(body, text="", bg=CARD, fg=MUTED, font=(FONT, 9),
                                  justify="left", anchor="w")
        self.auto_info.pack(fill="x", pady=(8, 0))
        self.auto_meter = tk.Canvas(body, width=430, height=32, bg=CARD, highlightthickness=0)
        self.auto_meter.pack(anchor="w", pady=(4, 0))
        self.auto_meter.create_text(0, 8, text=tr("Cena"), anchor="w", fill=MUTED, font=(FONT, 8))
        self.auto_meter.create_text(0, 24, text="Flash", anchor="w", fill=MUTED, font=(FONT, 8))
        self.auto_meter.create_rectangle(52, 3, 430, 13, fill=PANEL, outline="")
        self.auto_meter.create_rectangle(52, 19, 430, 29, fill=PANEL, outline="")
        self.meter_scene = self.auto_meter.create_rectangle(52, 3, 52, 13, fill=ACCENT, outline="")
        self.meter_out = self.auto_meter.create_rectangle(52, 19, 52, 29, fill=WARN, outline="")

        # ---- engrenagem
        row = [0]

        def head(oid, title):
            self._fx_head(gear, row[0], oid, title)
            row[0] += 1

        def plain(title):
            self._plain_head(gear, row[0], title)
            row[0] += 1

        def slider(key, text, lo, hi, fx=None, unit="%"):
            self._auto_slider(gear, row[0], text, key, lo, hi, unit, fx)
            row[0] += 1

        def combo(key, text, labels, cast=str, fx=None):
            var = self._auto_combo(gear, row[0], text, key, labels, cast, fx)
            row[0] += 1
            return var

        plain(tr("Como aplicar o brilho"))
        self.v_method = combo("method", tr("Método ao escurecer"), BRIGHT_METHOD_LABELS)
        self.v_method_up = combo("method_up", tr("Método ao clarear"), BRIGHT_METHOD_LABELS)
        tk.Button(gear, text=tr("Testar brilho (descobrir qual método funciona)"),
                  command=self.open_brightness_test, bg=PANEL, fg=TEXT, activebackground=BORDER,
                  activeforeground=TEXT, relief="flat", bd=0, padx=12, pady=5, font=(FONT, 9),
                  cursor="hand2").grid(row=row[0], column=0, columnspan=3, sticky="w", pady=(6, 0))
        row[0] += 1
        plain(tr("Brilho no jogo"))
        slider("boost", tr("Brilho máximo no jogo"), 100, BRIGHT_MAX)
        head("flash", tr("Escurecer rápido em flashes"))
        slider("flash_sens", tr("Sensibilidade ao flash"), 0, 100, "flash")
        slider("flash_amount", tr("Quanto escurece"), 5, 60, "flash")
        slider("flash_release", tr("Velocidade para voltar"), 1, 100, "flash")
        plain(tr("Como medir a imagem"))
        combo("measure", tr("Medir pela"), MEASURE_LABELS)
        combo("area", tr("Área medida"), AREA_LABELS)
        head("comp", tr("Descontar o brilho já aplicado na medição"))
        head("center", tr("Dar mais peso ao centro da tela"))
        combo("center", tr("Peso do centro"), CENTER_LABELS, int, "center")
        head("step", tr("Ignorar mudanças pequenas"))
        slider("step", tr("Mudança mínima"), 1, 10, "step")
        head("hotkey", tr("Tecla de atalho para ligar/desligar"))
        name = tk.Label(gear, text=tr("Tecla"), bg=CARD, fg=TEXT, font=(FONT, 9))
        name.grid(row=row[0], column=0, sticky="w", padx=(0, 14), pady=(6, 0))
        self.v_bright_key = tk.StringVar(value=label_of(BRIGHT_LABELS, d["hotkey"]))
        key_box = self._combo(gear, self.v_bright_key, [t for _k, t in BRIGHT_LABELS], width=14)
        key_box.grid(row=row[0], column=1, sticky="w", pady=(6, 0))
        key_box.bind("<<ComboboxSelected>>", self._on_bright_key)
        self._fx_attach("hotkey", [name, key_box])
        row[0] += 1
        tk.Label(gear, text=tr("O Windows limita quanto a curva da tela pode mudar; se recusar um "
                            "valor, o programa usa o maior que ele aceitar. Só a tela principal é "
                            "alterada, e ela volta ao normal quando você fecha o programa. A "
                            "proteção de flash funciona melhor com o jogo em janela ou tela cheia "
                            "sem borda."),
                 bg=CARD, fg=MUTED, font=(FONT, 8), wraplength=820, justify="left").grid(
                     row=row[0], column=0, columnspan=3, sticky="w", pady=(12, 4))

    # ---- shaders (visual do jogo) ----------------------------------------

    def _build_shader_card(self, parent):
        sh = self.settings["shader"]
        body, self.shader_badge, self.shader_status, gear = self._mod_card(
            parent, 2, 0, "Shaders",
            tr("Muda as cores e o contraste da tela inteira, como um filtro de vídeo. Escolha um "
            "visual pronto e, na engrenagem ⚙, ajuste cada coisa. Funciona junto com o brilho."),
            PINK, span=2)
        quick = tk.Frame(body, bg=CARD)
        quick.pack(anchor="w")
        self.sw_shader = self._switch_row(quick, 0, tr("Ligar shader"), sh["on"], self._on_shader_toggle)
        self._switch_row(quick, 1, tr("Só dentro do jogo"), sh["only_game"], self._on_shader_only)
        grid = tk.Frame(body, bg=CARD)
        grid.pack(anchor="w", pady=(8, 0))
        for i, name in enumerate(SHADER_PRESETS):
            btn = tk.Button(grid, text=name, width=11, bg=PANEL, fg=TEXT, activebackground=BORDER,
                            activeforeground=TEXT, relief="flat", bd=0, pady=6, font=(FONT, 9),
                            cursor="hand2", command=lambda n=name: self._shader_preset(n))
            btn.grid(row=i // 4, column=i % 4, padx=(0, 8), pady=(0, 6))
            self._shader_buttons[name] = btn
        self.shader_desc = tk.Label(body, text="", bg=CARD, fg=MUTED, font=(FONT, 9),
                                    justify="left", anchor="w")
        self.shader_desc.pack(fill="x", pady=(2, 0))

        row = [0]

        def slider(key, text, lo, hi, unit="%"):
            self._auto_slider(gear, row[0], text, key, lo, hi, unit, None, "shader",
                              self._shader_after)
            row[0] += 1

        slider("brightness", tr("Brilho do filtro (clareia ou escurece tudo)"), -100, 100)
        slider("contrast", tr("Contraste (mais punch ou mais desbotado)"), -100, 100)
        slider("saturation", tr("Saturação (0 = preto e branco)"), 0, 200)
        slider("warmth", tr("Calor (azul frio a laranja quente)"), -100, 100)
        slider("tint", tr("Matiz (verde a magenta)"), -100, 100)
        slider("amount", tr("Força do shader"), 0, 100)
        tk.Button(gear, text=tr("Zerar ajustes"), command=self._shader_reset, bg=PANEL, fg=TEXT,
                  activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0, padx=12,
                  pady=5, font=(FONT, 9), cursor="hand2").grid(
                      row=row[0], column=0, sticky="w", pady=(10, 0))
        self._shader_paint_buttons()

    def _shader_paint_buttons(self):
        current = self.settings["shader"]["preset"]
        for name, btn in self._shader_buttons.items():
            btn.config(bg=ACCENT if name == current else PANEL,
                       fg="white" if name == current else TEXT)
        self.shader_desc.config(text=SHADER_PRESETS[current][0] if current in SHADER_PRESETS else "")

    def _shader_set_values(self, values):
        self._shader_loading = True          # mexida do programa, não do usuário
        try:
            for key, value in values.items():
                self._auto_scales[f"shader.{key}"].set(value)
        finally:
            self._shader_loading = False

    def _shader_preset(self, name):
        _desc, bright, contrast, sat, warm, tint = SHADER_PRESETS[name]
        self.settings["shader"]["preset"] = name
        self._shader_set_values({"brightness": bright, "contrast": contrast, "saturation": sat,
                                 "warmth": warm, "tint": tint, "amount": 100})
        self.settings["shader"]["on"] = True
        self.sw_shader.set(True)
        self._shader_paint_buttons()
        self._shader_eval()

    def _shader_reset(self):
        self.settings["shader"]["preset"] = ""
        self._shader_set_values(SHADER_DEFAULT)
        self._shader_paint_buttons()
        self._shader_eval()

    def _on_shader_toggle(self, value):
        self.settings["shader"]["on"] = bool(value)
        self._tune()
        self._shader_eval()

    def _on_shader_only(self, value):
        self.settings["shader"]["only_game"] = bool(value)
        self._tune()
        self._shader_eval()

    def _shader_after(self):
        """Mexeu num slider: aplica daqui a pouco (junta vários movimentos seguidos)."""
        if not self._shader_loading:
            self.settings["shader"]["preset"] = ""
        if self._shader_job is not None:
            try:
                self.root.after_cancel(self._shader_job)
            except Exception:
                pass
        self._shader_job = self.root.after(60, self._shader_eval)

    def _shader_eval(self):
        try:
            self._shader_job = None
            sh = self.settings["shader"]
            want = bool(sh["on"])
            if want and sh["only_game"]:
                try:
                    want = foreground_exe() == self.settings["game"].lower()
                except Exception:
                    want = False
            key = (True,) + tuple(sh[k] for k in SHADER_DEFAULT) if want else (False,)
            if key == self._shader_key:
                return
            self._shader_key = key
            ok = shader_apply(grade_matrix(sh)) if want else shader_clear()
            if want and not ok:
                self._shader_key = None
                self.shader_badge.config(text=tr("NÃO CONSEGUI"), fg=WARN)
                self.shader_status.config(
                    text=tr("O Windows recusou o filtro de cor. O shader usa o mesmo recurso do método "
                         "'Filtro de cor' do brilho."), fg=WARN)
            elif want:
                name = sh["preset"] or "personalizado"
                self.shader_badge.config(text=tr('ATIVO · {}').format(name), fg=GREEN)
                self.shader_status.config(text=tr("Shader aplicado."), fg=GREEN)
            else:
                waiting = sh["on"] and sh["only_game"]
                self.shader_badge.config(text=tr("ESPERANDO O JOGO") if waiting else tr("DESLIGADO"),
                                         fg=ACCENT if waiting else MUTED)
                self.shader_status.config(text="", fg=MUTED)
        except Exception:
            write_error_log(tr("Erro no shader:\n") + traceback.format_exc())

    # ---- ajustes de jogo do Windows (MMCSS) ---------------------------------

    # ---- extras: limpeza, rede, tempo de jogo --------------------------

    def _build_extra_cards(self, parent):
        self._build_clean_card(parent)
        self._build_net_card(parent)
        self._build_playtime_card(parent)
        self._build_gamebar_card(parent)
        self._build_hotkeys_card(parent)

    def _build_gamebar_card(self, parent):
        body, _badge, self.gb_status, _gear = self._mod_card(
            parent, 7, 0, "Xbox Game Bar",
            tr("Desliga a gravação em segundo plano do Xbox Game Bar (Game DVR), que gasta um pouco de "
            "FPS e disco enquanto você joga. Só mexe nas configurações do seu usuário e dá para "
            "desfazer. Pode precisar reabrir o jogo."), ACCENT)
        buttons = tk.Frame(body, bg=CARD)
        buttons.pack(anchor="w")
        self._btn(buttons, tr("Desligar gravação"), self.gb_off_click, True).pack(side="left")
        self._btn(buttons, tr("Desfazer"), self.gb_undo_click).pack(side="left", padx=8)
        self._gb_refresh()

    def _gb_refresh(self):
        off = gm_extras.gamebar_is_off()
        self._status(self.gb_status, "ok" if off else "info",
                     tr("Gravação em segundo plano: desligada.") if off
                     else tr("Gravação em segundo plano: como o Windows deixou."))

    def gb_off_click(self):
        try:
            before = gm_extras.gamebar_off()
            if not self.settings["gamebar_backup"]:         # guarda só o estado ORIGINAL
                self.settings["gamebar_backup"] = json.dumps(before)
            save_settings(self.settings)
            self.add_log("ok", tr("Xbox Game Bar: gravação em segundo plano desligada."))
        except Exception as exc:
            self._status(self.gb_status, "warn", tr('Não consegui mexer: {}').format(exc))
            return
        self._gb_refresh()

    def gb_undo_click(self):
        raw = self.settings["gamebar_backup"]
        if not raw:
            self._status(self.gb_status, "info", tr("Nada para desfazer: o programa não mudou nada."))
            return
        try:
            gm_extras.gamebar_restore(json.loads(raw))
            self.settings["gamebar_backup"] = ""
            save_settings(self.settings)
            self.add_log("ok", tr("Xbox Game Bar: voltou ao que estava."))
        except Exception as exc:
            self._status(self.gb_status, "warn", tr('Não consegui desfazer: {}').format(exc))
            return
        self._gb_refresh()

    def _build_hotkeys_card(self, parent):
        body, _badge, _status, _gear = self._mod_card(
            parent, 7, 1, tr("Atalhos de teclado"),
            tr("Teclas F6 a F10 que funcionam com o jogo aberto. A tecla também chega no jogo, então "
            "escolha uma que ele não use. Os atalhos dos overlays ficam na engrenagem dos Overlays."),
            ACCENT)
        grid = tk.Frame(body, bg=CARD)
        grid.pack(anchor="w")
        self._auto_combo(grid, 0, tr("Ligar/desligar o Game Mode"), "gamemode", HOTKEY_LABELS, str,
                         None, "hotkeys", lambda: None)
        self._auto_combo(grid, 1, tr("Ligar/desligar o Movement Helper"), "move", HOTKEY_LABELS, str,
                         None, "hotkeys", lambda: None)

    def _build_clean_card(self, parent):
        body, _badge, self.clean_status, gear = self._mod_card(
            parent, 5, 0, tr("Limpar temporários"),
            tr("Apaga arquivos com mais de 1 dia das pastas de lixo do Windows e dos logs do Roblox. "
            "Primeiro mostra quanto dá para liberar; só apaga quando você clicar em Apagar. "
            "Não mexe nos seus documentos."), TEAL)
        buttons = tk.Frame(body, bg=CARD)
        buttons.pack(anchor="w")
        self.clean_buttons = [self._btn(buttons, tr("Procurar"), self.clean_scan_click, True),
                              self._btn(buttons, tr("Apagar"), self.clean_delete_click)]
        self.clean_buttons[0].pack(side="left")
        self.clean_buttons[1].pack(side="left", padx=8)
        self.clean_buttons[1].config(state="disabled")
        pastas = "\n".join(f"\u2022 {label}: {path}" for label, path in gm_extras.junk_roots())
        tk.Label(gear, text=tr("Pastas olhadas:\n") + (pastas or tr("nenhuma encontrada")), bg=CARD,
                 fg=MUTED, font=(FONT, 9), justify="left", wraplength=420).grid(
                     row=0, column=0, sticky="w")

    def clean_scan_click(self):
        self._busy(self.clean_buttons, True)
        self._status(self.clean_status, "info", "Procurando...")

        def done(result):
            self._busy(self.clean_buttons[:1], False)
            if isinstance(result, tuple):  # erro vindo do _run_bg
                self._status(self.clean_status, "warn", result[1][0][1])
                return
            self._clean_scan = result
            n = len(result["files"])
            total = sum(size for _p, size in result["files"])
            if not n:
                self._status(self.clean_status, "ok", tr("Nada para limpar. Está tudo em dia."))
                return
            lines = [tr('Dá para liberar {} em {} arquivo(s):').format(gm_extras.human_size(total), n)]
            lines += [f"\u2022 {label}: {gm_extras.human_size(size)} ({count})"
                      for label, (count, size) in result["by"].items() if count]
            self._status(self.clean_status, "info", "\n".join(lines))
            self.clean_buttons[1].config(state="normal")

        self._run_bg(lambda: gm_extras.scan_junk(gm_extras.junk_roots()), done)

    def clean_delete_click(self):
        scan = self._clean_scan
        if not scan or not scan["files"]:
            return
        total = sum(size for _p, size in scan["files"])
        if not messagebox.askyesno(
                tr("Apagar temporários"),
                tr('Apagar {} arquivo(s) ({})?\nIsso não dá para desfazer.').format(len(scan['files']), gm_extras.human_size(total))):
            return
        self._busy(self.clean_buttons, True)
        self._status(self.clean_status, "info", "Apagando...")
        self._clean_scan = None

        def done(result):
            self._busy(self.clean_buttons[:1], False)
            if not isinstance(result, tuple) or len(result) != 3:
                self._status(self.clean_status, "warn", tr("Não consegui apagar."))
                return
            freed, ok, left = result
            text = tr('Liberei {} ({} arquivo(s)).').format(gm_extras.human_size(freed), ok)
            if left:
                text += tr(' {} estavam em uso e ficaram.').format(left)
            self._status(self.clean_status, "ok", text)
            self.add_log("ok", text)

        self._run_bg(lambda: gm_extras.delete_junk(scan), done)

    def _build_net_card(self, parent):
        body, _badge, self.net_status, gear = self._mod_card(
            parent, 5, 1, tr("Rede"),
            tr("Testa a conexão com o servidor (tempo para abrir, variação e perda) e limpa o cache "
            "de DNS. Não é o ping de dentro do jogo, mas mostra se a rede está estável."), ACCENT)
        buttons = tk.Frame(body, bg=CARD)
        buttons.pack(anchor="w")
        self.net_buttons = [self._btn(buttons, tr("Testar conexão"), self.net_test_click, True),
                            self._btn(buttons, tr("Limpar DNS"), self.net_dns_click)]
        self.net_buttons[0].pack(side="left")
        self.net_buttons[1].pack(side="left", padx=8)
        tk.Label(gear, text=tr("O servidor testado é o mesmo do ping dos overlays "
                            "(muda lá, na engrenagem dos Overlays)."),
                 bg=CARD, fg=MUTED, font=(FONT, 9), justify="left", wraplength=420).grid(
                     row=0, column=0, columnspan=2, sticky="w")
        self._auto_slider(gear, 1, tr("Avisar se o ping passar de (0 desliga)"), "ping_alert", 0, 500,
                          " ms", None, "extras", lambda: None)

    def net_test_click(self):
        host = self.settings["overlay"]["ping_host"]
        if not host:
            self._status(self.net_status, "warn", tr("Este jogo não tem servidor. Digite um na "
                                                  "engrenagem dos Overlays (Servidor do ping)."))
            return
        self._busy(self.net_buttons, True)
        self._status(self.net_status, "info", tr('Testando {}...').format(host))

        def done(result):
            self._busy(self.net_buttons, False)
            if not isinstance(result, dict):
                self._status(self.net_status, "warn", tr("Não consegui testar."))
                return
            if result["lost"] == result["sent"]:
                self._status(self.net_status, "warn",
                             tr('Sem resposta de {}. Confira a internet.').format(result['host']))
                return
            bad = result["lost"] > 0 or result["jitter"] > 30
            verdict = tr("Conexão instável.") if bad else tr("Conexão estável.")
            text = (tr('{}: média {} ms (mín {}, máx {}), variação {} ms, perda {}/{}. ').format(result['host'], f'{result['avg']:.0f}', f'{result['min']:.0f}', f'{result['max']:.0f}', f'{result['jitter']:.0f}', result['lost'], result['sent'])
                    + verdict)
            self._status(self.net_status, "warn" if bad else "ok", text)
            self.add_log("warn" if bad else "ok", text)

        self._run_bg(lambda: gm_extras.tcp_probe(host), done)

    def net_dns_click(self):
        self._busy(self.net_buttons, True)
        self._status(self.net_status, "info", tr("Limpando o DNS..."))

        def done(result):
            self._busy(self.net_buttons, False)
            ok, msg = result if (isinstance(result, tuple) and len(result) == 2
                                 and isinstance(result[0], bool)) else (False, tr("Não consegui limpar."))
            if not isinstance(msg, str):
                msg = tr("Não consegui limpar.")
            self._status(self.net_status, "ok" if ok else "warn", msg)
            self.add_log("ok" if ok else "warn", msg)

        self._run_bg(gm_extras.flush_dns, done)

    def _build_playtime_card(self, parent):
        body, _badge, self.pt_status, gear = self._mod_card(
            parent, 6, 0, tr("Tempo de jogo"),
            tr("Conta quanto tempo o jogo escolhido ficou aberto, por dia. Fica só neste PC. "
            "Dá para ligar um lembrete de pausa (um bipe e um aviso na lista)."), GREEN, span=2)
        self.pt_label = tk.Label(body, text="", bg=CARD, fg=TEXT, font=(FONT, 10), justify="left")
        self.pt_label.pack(anchor="w")
        ex = self.settings["extras"]
        self.sw_break = self._switch_row(gear, 0, tr("Lembrar de fazer pausa"), ex["break_on"],
                                         self._break_toggle)
        self.v_break_min = tk.StringVar(value=str(ex["break_min"]))
        entry = self._entry(gear, self.v_break_min, 5)
        self._field(gear, 1, tr("Avisar a cada (minutos, 15 a 240)"), entry)
        entry.bind("<Return>", lambda _e: self._break_minutes())
        entry.bind("<FocusOut>", lambda _e: self._break_minutes())
        self._refresh_extra_state()

    def _break_toggle(self, on):
        self.settings["extras"]["break_on"] = bool(on)
        self._pt_next_break = None
        save_settings(self.settings)

    def _break_minutes(self):
        try:
            value = max(15, min(240, int(self.v_break_min.get().strip())))
        except ValueError:
            value = self.settings["extras"]["break_min"]
        self.v_break_min.set(str(value))
        if value != self.settings["extras"]["break_min"]:
            self.settings["extras"]["break_min"] = value
            self._pt_next_break = None
            save_settings(self.settings)

    def _refresh_extra_state(self):
        if gm_extras is None or self._pt is None or not hasattr(self, "pt_label"):
            return
        today, week, total = gm_extras.playtime_summary(self._pt)
        sess = gm_extras.fmt_hm(self._pt_session) if self._pt_session else "\u2014"
        self._cfg(self.pt_label, text=tr('Hoje: {}     ·     7 dias: {}     ·     Total: {}     ·     Sessão agora: {}').format(gm_extras.fmt_hm(today), gm_extras.fmt_hm(week), gm_extras.fmt_hm(total), sess))

    # ---- atualização automática ---------------------------------------

    def _upd_say(self, text, level="info"):
        self.add_log(level, text)
        label = self._upd_status
        try:
            if label is not None and label.winfo_exists():
                label.config(text=text)
        except Exception:
            pass

    def _upd_check(self, manual=False, status=None):
        """Procura versão nova em segundo plano. A única conexão é com o GitHub do projeto."""
        if gm_extras is None or self._upd_busy:
            return
        if status is not None:
            self._upd_status = status
        self._upd_busy = True
        self.settings["updates"]["last_check"] = time.time()

        def work():
            manifest = None
            try:
                manifest = gm_extras.fetch_manifest(UPDATE_MANIFEST_URL, UPDATE_REPO)
            finally:
                self._upd_result = (manifest, manual)
                self._upd_busy = False

        threading.Thread(target=work, daemon=True).start()
        if manual:
            self._upd_say(tr("Procurando atualização..."))

    def _update_tick(self):
        """Roda a cada atualização da janela: reage ao que os threads acharam e procura de tempos em tempos."""
        if gm_extras is None:
            return
        if self._upd_ready is not None:
            ready, self._upd_ready = self._upd_ready, None
            self._upd_installed(ready)
        if self._upd_result is not None:
            (manifest, manual), self._upd_result = self._upd_result, None
            self._upd_handle(manifest, manual)
        u, now = self.settings["updates"], time.time()
        if (u["mode"] != "off" and not self._upd_busy and not self._upd_installing
                and now - self._boot_at > 10 and now - u["last_check"] > 6 * 3600):
            self._upd_check()

    def _upd_handle(self, manifest, manual):
        current = APP_VERSION.split(" ")[0]
        if manifest is None:
            if manual:
                self._upd_say(tr("Não consegui procurar atualização (sem internet, ou ainda não há versão "
                              "publicada)."), "warn")
            return
        version = manifest["version"]
        if not gm_extras.is_newer(version, APP_VERSION):
            if manual:
                self._upd_say(tr('Você já está na versão mais nova ({}).').format(current), "ok")
            return
        u = self.settings["updates"]
        action = gm_extras.update_action(u["mode"], is_frozen(), version, u["skip"],
                                         self._roblox_running(), manual)
        if action == "wait":                     # jogo aberto: tenta de novo em 10 minutos
            u["last_check"] = time.time() - 6 * 3600 + 600
        elif action == "install":
            self._upd_install(manifest)
        elif action == "prompt":
            text = tr('Chegou a versão {} do Game Mode (você tem a {}).').format(version, current)
            if manifest["notes"].strip():
                text += "\n\n" + manifest["notes"].strip()[:500]
            text += tr("\n\nAtualizar agora? O programa fecha, atualiza e abre de novo sozinho.")
            if messagebox.askyesno("Game Mode", text, parent=self.root):
                self._upd_install(manifest)
            else:
                u["skip"] = version
                save_settings(self.settings)
                self._upd_say(tr('Atualização {} adiada. Dá para instalar depois em Opções, Atualizações.').format(version))
        elif action == "notify" and (manual or version not in self._upd_notified):
            self._upd_notified.add(version)
            self._upd_say(tr('Versão {} disponível. Baixe em {}').format(version, UPDATE_PAGE))
            if manual or messagebox.askyesno("Game Mode", tr('Chegou a versão {} do Game Mode.\n\nAbrir a página de download?').format(version), parent=self.root):
                import webbrowser
                webbrowser.open(UPDATE_PAGE)

    def _upd_install(self, manifest):
        if self._upd_installing:
            return
        self._upd_installing = True
        dest = os.path.join(tempfile.gettempdir(), "GameModeUpdate",
                            f"Instalar_GameMode_{manifest['version']}.exe")
        self._upd_say(tr('Baixando a versão {}...').format(manifest['version']))

        def work():
            try:
                self._upd_ready = ("ok", gm_extras.download_installer(manifest, dest))
            except Exception as exc:
                self._upd_ready = ("erro", str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _upd_installed(self, ready):
        self._upd_installing = False
        kind, value = ready
        if kind != "ok":
            self._upd_say(tr('Não consegui baixar a atualização: {}').format(value), "warn")
            return
        try:
            subprocess.Popen([value, "/S"], close_fds=True, creationflags=0x00000008 | 0x00000200)
        except OSError as exc:
            self._upd_say(tr('Não consegui abrir o instalador: {}').format(exc), "warn")
            return
        self._upd_say(tr("Atualizando o Game Mode... ele abre de novo sozinho."), "ok")
        self.on_close()

    def _ping_alert_tick(self, now):
        """Mede o ping em segundo plano (a cada 10 s) e avisa se ficar ruim por 2 medidas seguidas."""
        limit = self.settings["extras"]["ping_alert"]
        host = self.settings["overlay"]["ping_host"]
        if not limit or not host:
            return
        if not self._ping_busy and now - self._ping_at >= 10:
            self._ping_at, self._ping_busy = now, True

            def work():
                try:
                    result = gm_extras.tcp_probe(host, count=2, timeout=1.5)
                except Exception:
                    result = None
                self._ping_last = result
                self._ping_new = True
                self._ping_busy = False

            threading.Thread(target=work, daemon=True).start()
        if self._ping_new:
            self._ping_new = False
            r = self._ping_last
            bad = r is not None and (r["lost"] == r["sent"] or r["avg"] > limit)
            self._ping_bad = self._ping_bad + 1 if bad else 0
            if self._ping_bad >= 2 and now - self._ping_alert_at > 120:
                self._ping_alert_at = now
                what = tr("sem resposta do servidor") if r["lost"] == r["sent"] else f"{r['avg']:.0f} ms"
                self.notify("warn", tr('Ping alto ({}; limite {} ms).').format(what, limit))
                self._beep(True)

    def _playtime_tick(self):
        """Soma o tempo com o jogo aberto. Roda a cada atualização, mesmo minimizado."""
        if gm_extras is None or self._pt is None:
            return
        now = time.time()
        last, self._pt_last = self._pt_last, now
        if not self._roblox_running_cached():
            if self._pt_session:                      # o jogo fechou: fim da sessão
                self.add_log("info", tr('Sessão terminou: {} de jogo.').format(gm_extras.fmt_hm(self._pt_session)))
                self._pt_session = 0.0
                self._ping_bad = 0
                self._pt_next_break = None
                gm_extras.save_playtime(PLAYTIME_PATH, self._pt)
            return
        if last is None:
            return
        delta = min(now - last, 5.0)                  # o PC dormiu? não conta o buraco
        gm_extras.add_seconds(self._pt, delta, now)
        self._pt_session += delta
        ex = self.settings["extras"]
        if ex["break_on"]:
            limit = ex["break_min"] * 60
            if self._pt_next_break is None:
                self._pt_next_break = limit * (int(self._pt_session // limit) + 1)
            if self._pt_session >= self._pt_next_break:
                self._pt_next_break += limit
                self.notify("warn", tr('Você joga há {}. Que tal uma pausa?').format(gm_extras.fmt_hm(self._pt_session)))
                self._beep(True)
        self._ping_alert_tick(now)
        if now - self._pt_saved_at > 60:
            self._pt_saved_at = now
            gm_extras.save_playtime(PLAYTIME_PATH, self._pt)

    def _build_wintweaks_card(self, parent):
        body, self.wt_badge, self.wt_status, gear = self._mod_card(
            parent, 4, 0, tr("Windows para jogos"),
            tr("Ajustes do próprio Windows que dão mais prioridade a jogos (agendador multimídia). "
            "Pede permissão de administrador, guarda os valores de antes e dá para desfazer. Pode "
            "ajudar um pouco, mas não prometo mais FPS: depende do PC."), WARN, span=2)
        buttons = tk.Frame(body, bg=CARD)
        buttons.pack(anchor="w")
        self.wt_buttons = [self._btn(buttons, tr("Aplicar"), self.wintweaks_apply_click, True),
                           self._btn(buttons, tr("Desfazer"), self.wintweaks_restore_click)]
        self.wt_buttons[0].pack(side="left")
        self.wt_buttons[1].pack(side="left", padx=8)
        lines = []
        for sub, name, value, kind in WIN_TWEAKS:
            where = "Tasks\\Games" if sub else "SystemProfile"
            shown = "0xFFFFFFFF" if value == 0xFFFFFFFF else value
            lines.append(f"• {where}: {name} = {shown}")
        tk.Label(gear, text="O que muda (HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\"
                            "Multimedia\\SystemProfile):\n" + "\n".join(lines),
                 bg=CARD, fg=MUTED, font=(FONT, 9), justify="left").grid(
                     row=0, column=0, sticky="w")

    def wintweaks_apply_click(self):
        self._busy(self.wt_buttons, True)
        self._status(self.wt_status, "info", tr("Aguardando a permissão de administrador do Windows..."))
        wt = self.settings["win_tweaks"]
        if wt.get("backup") is None and not win_tweaks_active():
            try:
                wt["backup"] = win_tweaks_read()    # guarda os valores de antes
                save_settings(self.settings)
            except Exception:
                wt["backup"] = None
        self._run_bg(win_tweaks_apply, lambda result: self._show_result(
            self.wt_status, result, self.wt_buttons, self.refresh_mod_badges))

    def wintweaks_restore_click(self):
        self._busy(self.wt_buttons, True)
        self._status(self.wt_status, "info", tr("Aguardando a permissão de administrador do Windows..."))
        backup = self.settings["win_tweaks"].get("backup")

        def done(result):
            if result[0]:
                self.settings["win_tweaks"]["backup"] = None
                save_settings(self.settings)
            self._show_result(self.wt_status, result, self.wt_buttons, self.refresh_mod_badges)

        self._run_bg(lambda: win_tweaks_restore(backup), done)

    # ---- overlays (HUD) ----------------------------------------------------

    def _fg_game(self):
        """O jogo está na frente? (com cache de 0,25 s para não consultar o Windows toda hora)"""
        now = time.monotonic()
        if now - self._fg_cache[0] > 0.25:
            try:
                value = foreground_exe() == self.settings["game"].lower()
            except Exception:
                value = False
            self._fg_cache = (now, value)
        return self._fg_cache[1]

    def _hotkey_move(self):
        if gm_mods is None or not getattr(self, "_mods_ok", False):
            return
        new = self.move is None
        self.sw_move.set(new)
        self.move_toggle(new)
        self._beep(new)

    def _hotkey_tick(self):
        """Atalhos globais (F6 a F10): ligar/desligar overlays e zerar a contagem do FNF."""
        delay = 500
        try:
            f = self.settings["fnf"]
            hk = self.settings["hotkeys"]
            vks = gm_extras.HOTKEY_VK if gm_extras else {}
            keys = {"toggle": vks.get(f["hotkey_toggle"]), "reset": vks.get(f["hotkey_reset"]),
                    "gamemode": vks.get(hk["gamemode"]), "move": vks.get(hk["move"])}
            for name, vk in keys.items():
                if vk is None:
                    self._hk_prev[name] = False
                    continue
                delay = 40
                down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
                if down and not self._hk_prev[name]:
                    if name == "toggle":
                        new = not self.settings["overlay"]["on"]
                        self.sw_hud_on.set(new)
                        self._on_hud_toggle(new)
                    elif name == "reset":
                        if self.hud_input.lanes is not None:
                            self.hud_input.lanes.reset()
                    elif name == "gamemode":
                        self.toggle()
                        self._beep(self.is_on())
                    elif name == "move":
                        self._hotkey_move()
                self._hk_prev[name] = down
        except Exception:
            pass
        self.root.after(delay, self._hotkey_tick)

    def _hud_tick(self):
        ov = self.settings["overlay"]
        try:
            want = bool(ov["on"]) and (self._fg_game() if ov["only_game"] else True)
            self._hud_n += 1
            self.hud_stats.set_active(want and (ov["show"]["stats"] or ov["show"].get("client", False)))
            self.hud_input.set_active(want and (ov["show"]["keys"] or ov["show"]["mouse"]
                                                or ov["show"]["cps"] or ov["show"].get("fnf", False)
                                                or ov["show"].get("client", False)))
            if want and self._hud_n % 15 == 1:
                self.hud_stats.poll()
            self.hud.set_visible(want)
            if want:
                self.hud.draw()
            if self.overlay.visible and self._hud_n % 8 == 0:
                self.overlay.keep_on_top()
        except Exception:
            write_error_log(tr("Erro nos overlays:\n") + traceback.format_exc())
        self.root.after(PERF["hud"] if ov["on"] else 400, self._hud_tick)

    def _build_overlay_card(self, parent):
        ov = self.settings["overlay"]
        body, self.hud_badge, self.hud_status, gear = self._mod_card(
            parent, 3, 0, "Overlays",
            tr("Mostra informações por cima do jogo: CPU, RAM e ping, as teclas que você aperta, "
            "cliques por segundo e uma mira. Não mexe no jogo (é só uma janela transparente que o "
            "mouse atravessa). Não mostra FPS do jogo: o Windows não entrega isso sem um programa "
            "à parte."), TEAL, span=2)
        quick = tk.Frame(body, bg=CARD)
        quick.pack(anchor="w")
        self.sw_hud_on = self._switch_row(quick, 0, tr("Ligar overlays"), ov["on"], self._on_hud_toggle)
        self._switch_row(quick, 1, tr("Só dentro do jogo"), ov["only_game"],
                         lambda v: ov.__setitem__("only_game", bool(v)))
        looks = tk.Frame(body, bg=CARD)
        looks.pack(anchor="w", pady=(8, 0))
        self._look_buttons = {}
        for name in HUD_LOOKS:
            btn = tk.Button(looks, text=name, width=12, bg=PANEL, fg=TEXT, activebackground=BORDER,
                            activeforeground=TEXT, relief="flat", bd=0, pady=6, font=(FONT, 9),
                            cursor="hand2", command=lambda n=name: self._hud_look(n))
            btn.pack(side="left", padx=(0, 8))
            self._look_buttons[name] = btn
        self.hud_desc = tk.Label(body, text="", bg=CARD, fg=MUTED, font=(FONT, 9), justify="left",
                                 anchor="w")
        self.hud_desc.pack(fill="x", pady=(4, 6))
        elements = tk.Frame(body, bg=CARD)
        elements.pack(anchor="w")
        self._hud_switches = {}
        items = [("stats", tr("CPU, RAM e ping")), ("keys", tr("Teclas (WASD)")),
                 ("mouse", tr("Mouse e CPS")), ("cps", tr("Gráfico de CPS")), ("crosshair", tr("Mira"))]
        if gm_extras is not None:
            items.append(("fnf", tr("Setas do Friday Night Funkin' (teclas, KPS, contagem)")))
            items.append(("client", tr("Visual Client (estilo Feather e Badlion)")))
        for i, (key, text) in enumerate(items):
            self._hud_switches[key] = self._switch_row(
                elements, i, text, ov["show"][key],
                lambda v, k=key: ov["show"].__setitem__(k, bool(v)))
        if gm_extras is not None:
            fnf_row = tk.Frame(body, bg=CARD)
            fnf_row.pack(anchor="w", pady=(8, 0))
            self._btn(fnf_row, tr("Zerar contagem do FNF"), self._fnf_reset).pack(side="left")
        # engrenagem
        row = [0]

        def slider(store, key, text, lo, hi, unit="%"):
            self._auto_slider(gear, row[0], text, key, lo, hi, unit, None, store, lambda: None)
            row[0] += 1

        def combo(key, text, labels):
            self._auto_combo(gear, row[0], text, key, labels, str, None, "crosshair", lambda: None)
            row[0] += 1

        self._plain_head(gear, row[0], tr("Tamanho e aparência"))
        row[0] += 1
        slider("overlay", "scale", tr("Tamanho"), 50, 200)
        slider("overlay", "opacity", tr("Opacidade"), 30, 100)
        self._plain_head(gear, row[0], "Ping")
        row[0] += 1
        tk.Label(gear, text=tr("Servidor do ping"), bg=CARD, fg=TEXT, font=(FONT, 9)).grid(
            row=row[0], column=0, sticky="w", padx=(0, 14), pady=(4, 0))
        self.v_ping_host = tk.StringVar(value=ov["ping_host"])
        host_entry = self._entry(gear, self.v_ping_host, 24)
        host_entry.grid(row=row[0], column=1, sticky="w", pady=(4, 0))
        host_entry.bind("<Return>", lambda _e: self._on_ping_host())
        host_entry.bind("<FocusOut>", lambda _e: self._on_ping_host())
        row[0] += 1
        self._plain_head(gear, row[0], tr("Mira"))
        row[0] += 1
        combo("shape", tr("Formato"), CROSS_SHAPE_LABELS)
        combo("color", tr("Cor"), CROSS_COLOR_LABELS)
        slider("crosshair", "size", tr("Tamanho da mira"), 3, 40, " px")
        slider("crosshair", "gap", tr("Espaço no centro"), 0, 20, " px")
        slider("crosshair", "thick", tr("Espessura"), 1, 6, " px")
        if gm_extras is not None:
            fnf = self.settings["fnf"]
            self._plain_head(gear, row[0], "Friday Night Funkin'")
            row[0] += 1
            self._auto_combo(gear, row[0], tr("Teclas das setas"), "preset", FNF_PRESET_LABELS, str,
                             None, "fnf", self._fnf_apply)
            row[0] += 1
            tk.Label(gear, text=tr("Personalizado (esq, baixo, cima, dir)"), bg=CARD, fg=TEXT,
                     font=(FONT, 9)).grid(row=row[0], column=0, sticky="w", padx=(0, 14), pady=(6, 0))
            keys_box = tk.Frame(gear, bg=CARD)
            keys_box.grid(row=row[0], column=1, sticky="w", pady=(6, 0))
            saved = (list(fnf["keys"]) + ["", "", "", ""])[:4]
            self.v_fnf_keys = [tk.StringVar(value=k) for k in saved]
            for var in self.v_fnf_keys:
                entry = self._entry(keys_box, var, 5)
                entry.pack(side="left", padx=(0, 6))
                entry.bind("<Return>", lambda _e: self._fnf_custom_changed())
                entry.bind("<FocusOut>", lambda _e: self._fnf_custom_changed())
            row[0] += 1
            self._auto_combo(gear, row[0], tr("Onde fica no vídeo"), "pos", FNF_POS_LABELS, str,
                             None, "fnf", lambda: None)
            row[0] += 1
            self._switch_row(gear, row[0], tr("Zerar a contagem sozinho depois de 15 s sem apertar"),
                             fnf["auto_reset"], self._fnf_auto)
            row[0] += 1
            self._plain_head(gear, row[0], tr("Atalhos (as teclas também chegam no jogo)"))
            row[0] += 1
            self._auto_combo(gear, row[0], tr("Ligar/desligar overlays"), "hotkey_toggle",
                             HOTKEY_LABELS, str, None, "fnf", lambda: None)
            row[0] += 1
            self._auto_combo(gear, row[0], tr("Zerar a contagem"), "hotkey_reset", HOTKEY_LABELS,
                             str, None, "fnf", lambda: None)
            row[0] += 1
            self._fnf_apply()
            cfg = self.settings["client"]
            self._plain_head(gear, row[0], tr("Visual Client (estilo Feather e Badlion)"))
            row[0] += 1
            self._auto_combo(gear, row[0], tr("Fundo das caixas"), "style", CLIENT_STYLE_LABELS, str,
                             None, "client", lambda: None)
            row[0] += 1
            self._auto_combo(gear, row[0], tr("Cor de destaque"), "accent", CROSS_COLOR_LABELS, str,
                             None, "client", lambda: None)
            row[0] += 1
            for key, text in gm_extras.CLIENT_MODULES:
                self._switch_row(gear, row[0], text, cfg[f"{key}_on"],
                                 lambda on, k=key: self._client_set(f"{k}_on", on))
                row[0] += 1
                slider("client", f"{key}_x", tr("      posição horizontal"), 0, 100)
                slider("client", f"{key}_y", tr("      posição vertical"), 0, 100)
            for key, text in (("keys_mouse", tr("Teclas: botões do mouse")), ("keys_cps", tr("Teclas: CPS nos botões")),
                              ("keys_space", tr("Teclas: barra de espaço")), ("keys_mods", tr("Teclas: Shift e Ctrl"))):
                self._switch_row(gear, row[0], text, cfg[key], lambda on, k=key: self._client_set(k, on))
                row[0] += 1
        self._hud_paint_looks()

    def _fnf_apply(self):
        """Passa as teclas e as opções do FNF para o leitor de teclas."""
        if gm_extras is None:
            return
        f = self.settings["fnf"]
        vks, labels = gm_extras.fnf_keys(f["preset"], f["keys"])
        self.hud_input.lane_vks = vks
        self.hud_input.lane_labels = labels
        self.hud_input.lanes.auto_reset_s = 15 if f["auto_reset"] else 0
        bad = not vks
        if bad:
            self._status(self.hud_status, "warn",
                         tr("Setas do FNF: use 4 teclas diferentes (letra, número, F1 a F24 ou "
                         "esquerda, baixo, cima, direita)."))
        elif self._fnf_warned:
            self._status(self.hud_status, "info", "")
        self._fnf_warned = bad

    def _client_set(self, key, on):
        self.settings["client"][key] = bool(on)

    def _fnf_custom_changed(self):
        self.settings["fnf"]["keys"] = [v.get().strip().lower() for v in self.v_fnf_keys]
        self._fnf_apply()

    def _fnf_auto(self, on):
        self.settings["fnf"]["auto_reset"] = bool(on)
        self._fnf_apply()

    def _fnf_reset(self):
        if self.hud_input.lanes is not None:
            self.hud_input.lanes.reset()

    def _hud_paint_looks(self):
        current = self.settings["overlay"]["look"]
        for name, btn in self._look_buttons.items():
            btn.config(bg=ACCENT if name == current else PANEL,
                       fg="white" if name == current else TEXT)
        self.hud_desc.config(text=HUD_LOOKS[current][0] if current in HUD_LOOKS else "")

    def _hud_look(self, name):
        ov = self.settings["overlay"]
        ov["look"] = name
        for key, value in HUD_LOOKS[name][1].items():
            ov["show"][key] = value
            self._hud_switches[key].set(value)
        self._hud_paint_looks()
        prof = self._profile_for_game()
        if prof is not None:
            prof["look"] = name

    def _on_hud_toggle(self, value):
        self.settings["overlay"]["on"] = bool(value)
        self.hud_badge.config(text=tr("LIGADO") if value else tr("DESLIGADO"), fg=GREEN if value else MUTED)
        self._tune()

    def _on_ping_host(self):
        host = self.v_ping_host.get().strip()
        if host != self.settings["overlay"]["ping_host"]:
            self.settings["overlay"]["ping_host"] = host
            self.hud_stats.set_host(host)
            prof = self._profile_for_game()
            if prof is not None:
                prof["ping_host"] = host

    # ---- teste guiado de brilho ----------------------------------------

    def _set_bright_method(self, key, method):
        """key = 'method' (escurecer) ou 'method_up' (clarear)."""
        self.settings["display"][key] = method
        try:
            (self.v_method_up if key == "method_up" else self.v_method).set(
                label_of(BRIGHT_METHOD_LABELS, method))
        except Exception:
            pass
        self.overlay.hide()
        restore_brightness()
        self._bright_current = 100
        self._bright_method = "normal"
        self._bright_kick(0)

    def open_brightness_test(self):
        try:
            self._open_brightness_test()
        except Exception:
            err = traceback.format_exc()
            write_error_log(tr("Teste de brilho falhou:\n") + err)
            self._bright_test = False
            messagebox.showerror(tr("Teste de brilho"), err[-700:])

    def _open_brightness_test(self):
        # (letra, método, nome, brilho do teste): A-C escurecem, D-F clareiam
        steps = [("A", "gamma", tr("Curva da tela"), 50), ("B", "mag", tr("Filtro de cor do Windows"), 50),
                 ("C", "overlay", tr("Camada sobre a tela"), 50),
                 ("D", "gamma", tr("Curva da tela"), 180), ("E", "mag", tr("Filtro de cor do Windows"), 180),
                 ("F", "overlay", tr("Camada sobre a tela"), 180)]
        win = tk.Toplevel(self.root)
        win.title(tr("Teste de brilho"))
        win.configure(bg=BG)
        win.transient(self.root)
        win.geometry("600x700+120+40")
        self._bright_test = True
        restore_brightness()
        self.overlay.hide()
        tk.Label(win, text=tr("Teste de brilho"), bg=BG, fg=TEXT, font=(FONT, 14, "bold")).pack(
            anchor="w", padx=22, pady=(18, 4))
        tk.Label(win, text=tr("São 6 testes: A, B e C ESCURECEM a tela; D, E e F CLAREIAM. Cada um usa "
                           "um método diferente. Olhe a tela e marque em quais você viu a mudança. "
                           "Aí o programa usa o melhor método para escurecer e o melhor para clarear."),
                 bg=BG, fg=MUTED, font=(FONT, 9), wraplength=550, justify="left").pack(
                     anchor="w", padx=22)
        status = tk.Label(win, text=tr("Clique em Iniciar."), bg=BG, fg=WARN, font=(FONT, 11, "bold"),
                          wraplength=550, justify="left")
        status.pack(anchor="w", padx=22, pady=(14, 4))
        accepted_label = tk.Label(win, text="", bg=BG, fg=MUTED, font=(FONT, 9),
                                  wraplength=550, justify="left")
        accepted_label.pack(anchor="w", padx=22)
        seen = {}
        boxes = []
        for letter, method, name, level in steps:
            seen[letter] = tk.BooleanVar(value=False)
            verb = tr("ESCURECER") if level < 100 else tr("CLAREAR")
            box = tk.Checkbutton(win, text=tr('Vi a tela {} no teste {} ({})').format(verb, letter, name),
                                 variable=seen[letter], bg=BG, fg=TEXT, selectcolor=PANEL,
                                 activebackground=BG, activeforeground=TEXT, font=(FONT, 10),
                                 bd=0, highlightthickness=0, state="disabled")
            box.pack(anchor="w", padx=22, pady=(6, 0))
            boxes.append(box)
        accepted = {}

        def clear():
            restore_brightness()
            self.overlay.hide()

        def apply(method, level):
            if method == "overlay":
                return self.overlay.set(level)
            applied, _used = set_brightness(level, method)
            return applied is not None

        def finish():
            clear()
            status.config(text=tr("Fim do teste. Marque o que você viu e clique em Usar."))
            accepted_label.config(text=tr("O Windows aceitou: ") + ", ".join(
                f"{letter} ({tr('sim') if ok else tr('não')})" for letter, ok in accepted.items()))
            for box in boxes:
                box.config(state="normal")
            use_btn.config(state="normal")

        def run(i):
            letter, method, name, level = steps[i]
            accepted[letter] = apply(method, level)
            verb = "escura" if level < 100 else "clara"
            status.config(text=tr('Teste {} ({}): ').format(letter, name)
                               + (tr('a tela deve estar mais {} agora...').format(verb) if accepted[letter]
                                  else tr("o Windows recusou este método.")))
            win.after(1800, lambda: (clear(), win.after(700, lambda: step(i + 1))))

        def step(i):
            if i >= len(steps):
                finish()
                return
            status.config(text=tr('Teste {}: prepare-se...').format(steps[i][0]))
            win.after(500, lambda: run(i))

        def start():
            start_btn.config(state="disabled")
            step(0)

        def close():
            clear()
            self._bright_test = False
            self._bright_current = 100
            self._bright_method = "normal"
            win.destroy()
            self._bright_kick(0)

        def best(letters):
            """Prefere curva > filtro > camada entre os que você viu."""
            ranked = [(m, l) for l, m, _n, _v in steps if l in letters and seen[l].get()]
            for method in ("gamma", "mag", "overlay"):
                if any(m == method for m, _l in ranked):
                    return method
            return None

        def use():
            dim, up = best("ABC"), best("DEF")
            if not dim and not up:
                messagebox.showinfo(
                    tr("Teste de brilho"),
                    tr("Nenhum método mudou a tela. Se o jogo está em tela cheia exclusiva, "
                    "troque para janela ou tela cheia sem borda. Também pode haver outro "
                    "programa mexendo no brilho (painel da NVIDIA/AMD, modo HDR, luz noturna)."),
                    parent=win)
                return
            if dim:
                self._set_bright_method("method", dim)
            if up:
                self._set_bright_method("method_up", up)
            self._bright_test = False
            win.destroy()
            names = dict(BRIGHT_METHOD_LABELS)
            text = (tr("Escurecer: ") + (names[dim] if dim else tr("nenhum funcionou")) + tr(" · "
                    "Clarear: ") + (names[up] if up else tr("nenhum funcionou")))
            self.bright_status.config(text=tr("Método escolhido pelo teste. ") + text + ".",
                                      fg=GREEN if (dim and up) else WARN)

        bar = tk.Frame(win, bg=BG)
        bar.pack(side="bottom", fill="x", padx=22, pady=16)
        start_btn = tk.Button(bar, text=tr("Iniciar"), command=start, bg=ACCENT, fg="white",
                              activebackground=ACCENT_HOVER, activeforeground="white", relief="flat",
                              bd=0, padx=20, pady=7, font=(FONT, 9, "bold"), cursor="hand2")
        start_btn.pack(side="left")
        use_btn = tk.Button(bar, text=tr("Usar o melhor"), command=use, bg=PANEL, fg=TEXT,
                            activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0,
                            padx=20, pady=7, font=(FONT, 9), cursor="hand2", state="disabled")
        use_btn.pack(side="left", padx=8)
        tk.Button(bar, text=tr("Cancelar"), command=close, bg=BG, fg=MUTED, activebackground=BG,
                  activeforeground=TEXT, relief="flat", bd=0, font=(FONT, 9),
                  cursor="hand2").pack(side="right")
        win.protocol("WM_DELETE_WINDOW", close)

    def _bright_kick(self, delay=80):
        if self._bright_job is not None:
            try:
                self.root.after_cancel(self._bright_job)
            except Exception:
                pass
        self._bright_job = self.root.after(delay, self._bright_eval)

    def _on_bright_slide(self, value):
        level = int(float(value))
        self.settings["display"]["level"] = level
        self.bright_value.config(text=f"{level}%")
        self._bright_kick()

    def _bright_preset(self, value):
        self.bright_scale.set(value)
        self._bright_kick(0)

    def _auto_worker(self):
        """Vigia a imagem do jogo ~10 vezes por segundo (só com a proteção de flash ligada e o
        jogo na frente) e calcula quanto escurecer."""
        guard = self._auto_brain
        last = time.monotonic()
        while not self._auto_stop.is_set():
            wait = 0.6
            try:
                d = self.settings["display"]
                if d["on"]["flash"] and foreground_exe() == self.settings["game"].lower():
                    wait = 0.1
                    now = time.monotonic()
                    sample = sample_luma(d["center"] if d["on"]["center"] else 1,
                                         d["area"] == "screen")
                    if d["on"]["comp"]:
                        sample = undo_brightness(sample, self._bright_current, self._bright_method)
                    dim = guard.update(sample, now, now - last, d)
                    last = now
                    self._flash_active = True
                    if dim is None:
                        self._auto_ok = False
                        self._flash_dim = 0.0
                    else:
                        self._auto_ok = True
                        self._auto_luma = guard.luma
                        self._flash_dim = dim
                else:
                    guard.reset()
                    self._flash_dim = 0.0
                    self._flash_active = False
                    last = time.monotonic()
            except Exception:
                self._flash_dim = 0.0
            self._auto_stop.wait(wait)

    def _update_auto_info(self):
        d = self.settings["display"]
        dim = self._flash_dim
        if not d["on"]["flash"]:
            text, badge, color = "", f"{self._bright_current}%", MUTED
        elif not self._flash_active:
            text = tr("Proteção de flash ligada. Ela começa quando o jogo ficar na frente.")
            badge, color = tr("FLASH · ESPERANDO"), ACCENT
        elif not self._auto_ok:
            text = tr("Não consegui ler a imagem do jogo (tela cheia exclusiva?). Sem proteção de flash.")
            badge, color = tr("FLASH · SEM LEITURA"), WARN
        elif dim > 1:
            text = tr('Flash detectado: escurecendo {}% (brilho {}%)').format(round(dim), self._bright_current)
            badge, color = tr('FLASH · -{}%').format(round(dim)), WARN
        else:
            text = tr('Vigiando: cena com {}% de claridade, sem flash.').format(round(self._auto_luma / 255 * 100))
            badge, color = tr("FLASH · VIGIANDO"), GREEN
        if self.auto_info.cget("text") != text:
            self.auto_info.config(text=text)
        if self.bright_badge.cget("text") != badge:
            self.bright_badge.config(text=badge, fg=color)
        active = d["on"]["flash"] and self._flash_active and self._auto_ok
        scene = self._auto_luma / 255.0 if active else 0.0
        out = (dim / max(1.0, float(d["flash_amount"]))) if active else 0.0
        self.auto_meter.coords(self.meter_scene, 52, 3, 52 + 378 * max(0.0, min(1.0, scene)), 13)
        self.auto_meter.coords(self.meter_out, 52, 19, 52 + 378 * max(0.0, min(1.0, out)), 29)

    def _on_gboost(self, value):
        self.settings["display"]["game_boost"] = bool(value)
        self._tune()
        self._bright_kick(0)

    def _on_bright_key(self, _event=None):
        key = key_of(BRIGHT_LABELS, self.v_bright_key.get())
        self.settings["display"]["hotkey"] = key
        self._tune()

    def bright_reset(self):
        """Brilho normal (100%) e jogo sem aumento."""
        try:
            self.sw_gboost.set(False)
            self.settings["display"]["game_boost"] = False
            self.bright_scale.set(100)
            self._bright_kick(0)
        except Exception:
            pass

    def _apply_brightness(self, target, method):
        """Aplica pelo método escolhido. Retorna (valor aplicado, método usado)."""
        if method == "overlay":
            restore_brightness()
            return (target, "overlay") if self.overlay.set(target) else (None, "")
        applied, used = set_brightness(target, method)
        if applied is None and method == "auto":
            if self.overlay.set(target):          # último recurso do automático
                return target, "overlay"
            return None, ""
        self.overlay.hide()
        return applied, used

    def _bright_eval(self):
        """Decide o brilho e aplica. Qualquer erro vira aviso (antes sumia calado)."""
        try:
            self._bright_eval_inner()
        except Exception:
            err = traceback.format_exc()
            write_error_log(tr("Erro no brilho:\n") + err)
            try:
                self.bright_status.config(text=tr("Erro no brilho: ") + err.strip().splitlines()[-1],
                                          fg=WARN)
                self.add_log("warn", tr("Erro no brilho: ") + err.strip().splitlines()[-1])
            except Exception:
                pass

    def _bright_eval_inner(self):
        """Decide qual brilho a tela deve ter agora e aplica se mudou."""
        self._bright_job = None
        if self._bright_test:
            return
        d = self.settings["display"]
        only_game = d["on"]["only_game"]
        fg_game = False
        if d["game_boost"] or only_game or d["on"]["flash"]:
            try:
                fg_game = foreground_exe() == self.settings["game"].lower()
            except Exception:
                fg_game = False
        if only_game and not fg_game:
            base = 100                              # fora do jogo a tela fica normal
        elif fg_game and d["game_boost"]:
            base = max(d["level"], d["boost"])      # brilho extra do jogo
        else:
            base = d["level"]
        dim = self._flash_dim if (fg_game and d["on"]["flash"]) else 0.0
        target = max(BRIGHT_MIN, int(round(base - dim)))
        step = d["step"] if d["on"]["step"] else 1
        if dim > 0 and target != base and abs(target - self._bright_current) < step:
            return  # mudança pequena demais: evita ficar piscando
        if target == self._bright_current:
            return
        self._bright_current = target
        applied, used = self._apply_brightness(
            target, d["method_up"] if target > 100 else d["method"])
        self._bright_method = used or "normal"
        how = {"gamma": tr("curva da tela"), "mag": tr("filtro de cor"),
               "overlay": tr("camada sobre a tela")}.get(used, "")
        if applied is None:
            self.bright_status.config(
                text=tr("O Windows e o driver recusaram mudar o brilho. Clique em \"Testar brilho\" "
                     "para achar um método que funcione."), fg=WARN)
            self.add_log("warn", tr("Não consegui mudar o brilho (recusado pelo Windows/driver)."))
        elif applied != target:
            self.bright_status.config(
                text=tr('Só consegui {}% (você pediu {}%) pela {}. Clique em "Testar brilho" para achar um método melhor.').format(applied, target, how), fg=WARN)
        else:
            if only_game and not fg_game:
                where = tr(" (fora do jogo: normal)")
            else:
                where = tr(" dentro do jogo") if fg_game else ""
            via = f" · {how}" if how else ""
            flash = tr(' · flash -{}%').format(round(dim)) if dim > 1 else ""
            self.bright_status.config(text=tr('Brilho aplicado: {}%{}{}{}.').format(applied, where, via, flash),
                                      fg=GREEN)

    def _bright_tick(self):
        """A cada instante: tecla de brilho e janela do jogo em primeiro plano."""
        d = self.settings["display"]
        try:
            key = self._bright_hotkey()
            if key != "none":
                state = user32.GetAsyncKeyState(BRIGHT_VK[key])
                down = bool(state & 0x8000)
                tapped = bool(state & 0x0001) and not down
                if (down or tapped) and not self._bright_key_down:
                    now = not d["game_boost"]
                    self.sw_gboost.set(now)
                    self._on_gboost(now)
                    self.add_log("info", tr("Brilho do jogo ") + ("ligado." if now else "desligado."))
                self._bright_key_down = down
            self._bright_n += 1
            if d["on"]["flash"] or ((d["game_boost"] or d["on"]["only_game"])
                                    and self._bright_n % 4 == 0):
                self._bright_eval()
            sh = self.settings["shader"]
            if sh["on"] and (sh["only_game"] or self._bright_n % 4 == 0):
                self._shader_eval()
            if self._bright_n % 2 == 0:
                self._update_auto_info()
            if self._bright_n % 8 == 0:
                self.overlay.keep_on_top()
        except Exception:
            pass
        self.root.after(120 if self._bright_realtime() else PERF["idle"], self._bright_tick)

    # ---- gerenciar apps (adicionar / remover) -------------------------

    def _running_choices(self):
        """Programas abertos agora que ainda não estão protegidos."""
        try:
            return running_program_names(exclude=set(self.settings["protect"]) | NOT_GAMES)
        except Exception:
            return []

    def _apply_fso_pref(self):
        """Otimizações de tela cheia desligadas nos jogos que pediram; religa o que o programa mudou e sobrou."""
        try:
            if gm_extras is None:
                return
            s = self.settings
            desired = set()
            for prof in s["profiles"]:
                if prof.get("fso"):
                    desired |= set(gpu_targets_for(prof["exe"], s))
            changed = fso_apply(sorted(desired), True) if desired else []
            stale = set(s["fso_paths"]) - desired
            back = fso_apply(sorted(stale), False) if stale else []
            s["fso_paths"] = sorted((set(s["fso_paths"]) | set(changed)) - stale)
            if changed:
                self.add_log("ok", tr('Otimizações de tela cheia desativadas para {} programa(s). Valem na próxima vez que o jogo abrir.').format(len(changed)))
            if back:
                self.add_log("ok", tr('Otimizações de tela cheia de volta ao normal ({}).').format(len(back)))
        except Exception:
            write_error_log("Otimizações de tela cheia falharam:\n" + traceback.format_exc())

    def _apply_gpu_pref(self):
        """GPU de alto desempenho para todos os jogos da lista que pediram; desfaz o que sobrou."""
        self._apply_fso_pref()
        try:
            s = self.settings
            desired = set()
            if gm_extras is not None:
                for prof in s["profiles"]:
                    if prof.get("gpu"):
                        desired |= set(gpu_targets_for(prof["exe"], s))
            elif s["gpu_pref"]:
                desired |= set(roblox_exes())
            changed = gpu_pref_apply(sorted(desired)) if desired else []
            stale = set(s["gpu_paths"]) - desired
            removed = gpu_pref_clear(sorted(stale)) if stale else 0
            s["gpu_paths"] = sorted((set(s["gpu_paths"]) | set(changed)) - stale)
            if changed:
                self.add_log("ok", tr('GPU de alto desempenho para {} programa(s). Vale na próxima vez que o jogo abrir.').format(len(changed)))
            if removed:
                self.add_log("ok", tr('Preferência de GPU desfeita ({}).').format(removed))
        except Exception:
            write_error_log(tr("GPU do jogo falhou:\n") + traceback.format_exc())

    def _restart_engine_if_on(self):
        if self.is_on():  # reinicia com as novas listas
            self.engine.stop()
            self.stopping = True
            self.pending_restart = True

    def open_apps_manager(self):
        try:
            self._open_apps_manager()
        except Exception:
            err = traceback.format_exc()
            write_error_log(tr("Lista de apps falhou:\n") + err)
            messagebox.showerror("Apps", tr("Não consegui abrir a lista de apps:\n\n") + err[-700:])

    def _open_apps_manager(self):
        if self._apps_win is not None:
            try:
                if self._apps_win.winfo_exists():
                    self._apps_win.deiconify()
                    self._apps_win.lift()
                    self._apps_win.focus_force()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._apps_win = win
        win.title(tr("Apps para deixar mais lentos"))
        win.configure(bg=BG)
        win.transient(self.root)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = min(820, sw - 80), min(600, sh - 100)
        win.geometry(f"{width}x{height}+{max(0, (sw - width) // 2)}+{max(0, (sh - height) // 3)}")
        win.minsize(680, 460)

        calm = {normalize_app_name(n) for n in self.settings["calm"] if normalize_app_name(n)}
        protect = {n.lower() for n in self.settings["protect"]}

        def small_button(parent, text, command, primary=False):
            return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else PANEL,
                             fg="white" if primary else TEXT, activebackground=BORDER,
                             activeforeground=TEXT, relief="flat", bd=0, padx=14, pady=6,
                             font=(FONT, 9, "bold" if primary else "normal"), cursor="hand2")

        tk.Label(win, text=tr("Escolha os apps que o Game Mode deve deixar mais lentos enquanto você joga."),
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=20, pady=(16, 8))

        bottom = tk.Frame(win, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=20, pady=14)
        manual = tk.Frame(win, bg=BG)
        manual.pack(side="bottom", fill="x", padx=20, pady=(0, 4))
        panes = tk.Frame(win, bg=BG)
        panes.pack(side="top", fill="both", expand=True, padx=20)
        panes.grid_columnconfigure(0, weight=1, uniform="p")
        panes.grid_columnconfigure(2, weight=1, uniform="p")
        panes.grid_rowconfigure(1, weight=1)

        def listbox_in(parent, row, col):
            frame = tk.Frame(parent, bg=PANEL)
            frame.grid(row=row, column=col, sticky="nsew")
            lb = tk.Listbox(frame, selectmode="extended", bg=PANEL, fg=TEXT,
                            selectbackground=ACCENT, selectforeground="#ffffff", relief="flat",
                            bd=0, highlightthickness=0, font=("Consolas", 10), activestyle="none",
                            exportselection=False)
            bar = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=bar.set)
            lb.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
            bar.pack(side="right", fill="y")
            return lb

        left_title = tk.StringVar()
        right_title = tk.StringVar()
        tk.Label(panes, textvariable=left_title, bg=BG, fg=TEXT, font=(FONT, 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        tk.Label(panes, textvariable=right_title, bg=BG, fg=TEXT, font=(FONT, 9, "bold")).grid(
            row=0, column=2, sticky="w", pady=(0, 4))
        left = listbox_in(panes, 1, 0)
        right = listbox_in(panes, 1, 2)

        search_var = tk.StringVar()
        search_row = tk.Frame(panes, bg=BG)
        search_row.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        search = tk.Entry(search_row, textvariable=search_var, bg=PANEL, fg=TEXT,
                          insertbackground=TEXT, relief="flat", font=(FONT, 10))
        search.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Label(search_row, text=tr(" buscar"), bg=BG, fg=MUTED, font=(FONT, 8)).pack(side="left")

        def refresh_left(*_args):
            try:
                running = running_program_names(exclude=protect | NOT_GAMES | calm)
            except Exception:
                running = []
            term = search_var.get().strip().lower()
            left.delete(0, "end")
            for name in running:
                if term in name:
                    left.insert("end", name)
            left_title.set(tr('Abertos agora ({})').format(left.size()))

        def refresh_right():
            right.delete(0, "end")
            for name in sorted(calm):
                right.insert("end", name)
            right_title.set(tr('Vão ficar mais lentos ({})').format(right.size()))

        def add_selected(_event=None):
            for i in left.curselection():
                calm.add(left.get(i))
            refresh_right()
            refresh_left()

        def remove_selected(_event=None):
            for i in right.curselection():
                calm.discard(right.get(i))
            refresh_right()
            refresh_left()

        search_var.trace_add("write", refresh_left)
        left.bind("<Double-Button-1>", add_selected)
        right.bind("<Double-Button-1>", remove_selected)
        right.bind("<Delete>", remove_selected)

        mid = tk.Frame(panes, bg=BG)
        mid.grid(row=1, column=1, padx=12)
        small_button(mid, tr("Adicionar  \u203A"), add_selected, True).pack(pady=(0, 8), fill="x")
        small_button(mid, tr("\u2039  Remover"), remove_selected).pack(fill="x")
        small_button(panes, tr("Atualizar lista"), refresh_left).grid(row=2, column=2, sticky="e",
                                                                  pady=(6, 0))

        manual_var = tk.StringVar()
        tk.Label(manual, text=tr("Não está na lista? Digite o nome:"), bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(side="left")
        entry = tk.Entry(manual, textvariable=manual_var, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=(FONT, 10), width=26)
        entry.pack(side="left", padx=8, ipady=4)

        def add_manual(_event=None):
            name = normalize_app_name(manual_var.get())
            if not name:
                return
            if name in protect:
                messagebox.showwarning(
                    "Apps", tr('{} está na lista de protegidos (Opções) e nunca é tocado.').format(name),
                    parent=win)
                return
            calm.add(name)
            manual_var.set("")
            refresh_right()
            refresh_left()

        entry.bind("<Return>", add_manual)
        small_button(manual, tr("Adicionar nome"), add_manual).pack(side="left")

        def close():
            self._apps_win = None
            win.destroy()

        def save():
            self.settings["calm"] = sorted(calm - protect)
            self.settings["unslow_active"] = bool(unslow_var.get())
            save_settings(self.settings)
            self.add_log("ok", tr('Lista atualizada: {} apps para deixar mais lentos.').format(len(self.settings['calm'])))
            close()
            self._restart_engine_if_on()

        def reset():
            calm.clear()
            calm.update(normalize_app_name(n) for n in DEFAULT_CALM)
            refresh_right()
            refresh_left()

        unslow_var = tk.BooleanVar(value=bool(self.settings.get("unslow_active", True)))
        tk.Checkbutton(win, text=tr("Se eu estiver usando um app da lista, deixar ele normal até eu sair dele"),
                       variable=unslow_var, bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG,
                       activeforeground=TEXT, font=(FONT, 9), bd=0, highlightthickness=0,
                       cursor="hand2").pack(side="bottom", anchor="w", padx=20, pady=(0, 6))
        small_button(bottom, tr("Salvar"), save, True).pack(side="right")
        small_button(bottom, tr("Cancelar"), close).pack(side="right", padx=8)
        tk.Button(bottom, text=tr("Restaurar padrões"), command=reset, bg=BG, fg=MUTED,
                  activebackground=BG, activeforeground=TEXT, relief="flat", bd=0,
                  font=(FONT, 9), cursor="hand2").pack(side="left")
        win.protocol("WM_DELETE_WINDOW", close)
        refresh_right()
        refresh_left()
        win.focus_force()

    # ---- opções ------------------------------------------------------

    def open_options(self):
        win = tk.Toplevel(self.root)
        win.title(tr("Opções"))
        win.configure(bg=BG)
        win.transient(self.root)
        sh = self.root.winfo_screenheight()
        win.geometry(f"580x{min(740, sh - 100)}")
        win.resizable(False, True)
        win.grab_set()

        bar = tk.Frame(win, bg=BG)  # botões sempre visíveis embaixo
        bar.pack(side="bottom", fill="x", padx=20, pady=14)
        scroll = ScrollFrame(win, BG)
        scroll.pack(side="top", fill="both", expand=True)
        body = scroll.inner

        def label(text, pady=(14, 4)):
            tk.Label(body, text=text, bg=BG, fg=TEXT, font=(FONT, 9, "bold")).pack(
                anchor="w", padx=20, pady=pady)

        def check(text, var):
            tk.Checkbutton(body, text=text, variable=var, bg=BG, fg=TEXT, selectcolor=PANEL,
                           activebackground=BG, activeforeground=TEXT, font=(FONT, 9),
                           anchor="w").pack(fill="x", padx=18)

        profs = [dict(p) for p in self.settings["profiles"]] if gm_extras is not None else []
        cur_prof = gm_extras.find_profile(profs, self.settings["game"]) if profs else None
        sel = [profs.index(cur_prof) if cur_prof is not None else 0]
        if gm_extras is not None:
            label(tr("Jogos (um perfil para cada jogo)"), pady=(16, 4))
            prof_row = tk.Frame(body, bg=BG)
            prof_row.pack(fill="x", padx=20)
            prof_pick = ttk.Combobox(prof_row, state="readonly", font=(FONT, 10))
            prof_pick.pack(side="left", fill="x", expand=True, ipady=3)
            btn_new = tk.Button(prof_row, text=tr("Novo jogo"), relief="flat", bd=0, bg=PANEL, fg=TEXT,
                                activebackground=BORDER, activeforeground=TEXT, padx=12, pady=5,
                                font=(FONT, 9), cursor="hand2")
            btn_new.pack(side="left", padx=(8, 0))
            btn_del = tk.Button(prof_row, text=tr("Remover"), relief="flat", bd=0, bg=PANEL, fg=TEXT,
                                activebackground=BORDER, activeforeground=TEXT, padx=12, pady=5,
                                font=(FONT, 9), cursor="hand2")
            btn_del.pack(side="left", padx=(8, 0))
            btn_imp = None
            if gm_games is not None:
                btn_imp = tk.Button(body, text=tr("Importar da Steam / Epic..."), relief="flat", bd=0, bg=PANEL,
                                    fg=TEXT, activebackground=BORDER, activeforeground=TEXT, padx=12,
                                    pady=5, font=(FONT, 9), cursor="hand2")
                btn_imp.pack(anchor="w", padx=20, pady=(8, 0))
            tk.Label(body, text=tr("Cada jogo guarda o próprio servidor de ping, visual do overlay e GPU. "
                                "O jogo mostrado aqui é o que o Game Mode usa."), bg=BG, fg=MUTED,
                     font=(FONT, 8), justify="left", wraplength=520).pack(anchor="w", padx=20, pady=(4, 0))
        label(tr("Programa do jogo"), pady=(16, 4))
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", padx=20)
        game_var = tk.StringVar(value=self.settings["game"])
        picker = ttk.Combobox(row, textvariable=game_var, values=self._program_choices(),
                              font=(FONT, 10))
        picker.pack(side="left", fill="x", expand=True, ipady=3)
        tk.Button(row, text=tr("Atualizar lista"), relief="flat", bd=0, bg=PANEL, fg=TEXT,
                  activebackground=BORDER, activeforeground=TEXT, padx=12, pady=5,
                  font=(FONT, 9), cursor="hand2",
                  command=lambda: picker.config(values=self._program_choices())).pack(
                      side="left", padx=(8, 0))
        tk.Label(body, text=tr("Abra o jogo e clique em Atualizar lista: ele aparece para escolher."),
                 bg=BG, fg=MUTED, font=(FONT, 8)).pack(anchor="w", padx=20, pady=(4, 0))
        tk.Label(body, text=tr("Mod do FNF (Psych Engine, Kade...) usa outro nome: abra o jogo e "
                            "use Atualizar lista."), bg=BG, fg=MUTED, font=(FONT, 8)).pack(
                                anchor="w", padx=20, pady=(4, 0))
        if gm_extras is not None:
            name_var, ping_var = tk.StringVar(), tk.StringVar()
            look_var, gpu_var = tk.StringVar(), tk.BooleanVar()
            auto_var = tk.BooleanVar(value=self.settings["auto_game"])
            fso_var = tk.BooleanVar()
            det = tk.Frame(body, bg=BG)
            det.pack(fill="x", padx=20, pady=(10, 0))
            look_box = ttk.Combobox(det, textvariable=look_var, values=list(HUD_LOOKS),
                                    state="readonly", width=16, font=(FONT, 9))
            for i, (text, widget) in enumerate((
                    (tr("Nome do jogo"), self._entry(det, name_var, 28)),
                    (tr("Servidor do ping"), self._entry(det, ping_var, 28)),
                    (tr("Visual do overlay"), look_box))):
                tk.Label(det, text=text, bg=BG, fg=TEXT, font=(FONT, 9)).grid(
                    row=i, column=0, sticky="w", pady=3, padx=(0, 14))
                widget.grid(row=i, column=1, sticky="w", pady=3)
            check(tr("GPU de alto desempenho neste jogo (vale na próxima vez que o jogo abrir)"), gpu_var)
            check(tr("Desativar otimizações de tela cheia neste jogo (só se o jogo travar ou tiver atraso)"), fso_var)
            check(tr("Trocar sozinho para o jogo da lista que você abrir"), auto_var)

            def entry_text(q):
                return f"{q['name']}  ({q['exe'] or 'escolha o programa'})"

            def load():
                q = profs[sel[0]]
                game_var.set(q["exe"])
                name_var.set(q["name"])
                ping_var.set(q["ping_host"])
                look_var.set(q["look"] if q["look"] in HUD_LOOKS else "Classic")
                gpu_var.set(bool(q["gpu"]))
                fso_var.set(bool(q.get("fso")))
                prof_pick.config(values=[entry_text(x) for x in profs])
                prof_pick.current(sel[0])

            def commit():
                q = profs[sel[0]]
                exe = gm_extras.normalize_exe(game_var.get())
                q["exe"] = exe
                q["name"] = name_var.get().strip() or (game_title(exe) if exe else tr("Novo jogo"))
                q["ping_host"] = ping_var.get().strip()
                q["look"] = look_var.get() if look_var.get() in HUD_LOOKS else "Classic"
                q["gpu"] = bool(gpu_var.get())
                q["fso"] = bool(fso_var.get())

            def pick(_event=None):
                commit()
                idx = prof_pick.current()
                if idx >= 0:
                    sel[0] = idx
                load()

            def add_profile():
                commit()
                profs.append(gm_extras.new_profile("", tr("Novo jogo")))
                sel[0] = len(profs) - 1
                load()

            def remove_profile():
                if len(profs) <= 1:
                    messagebox.showinfo(tr("Jogos"), tr("Precisa sobrar pelo menos um jogo."), parent=win)
                    return
                del profs[sel[0]]
                sel[0] = max(0, sel[0] - 1)
                load()

            def apply_profiles():
                """Confere os perfis e passa o escolhido para as configurações. False se algo está errado."""
                commit()
                chosen = profs[sel[0]]
                if not chosen["exe"]:
                    messagebox.showwarning(tr("Opções"), tr("Escolha ou digite o programa do jogo."), parent=win)
                    return False
                keep = [q for i, q in enumerate(profs) if q["exe"] or i == sel[0]]
                seen = set()
                for q in keep:
                    if q["exe"].lower() in seen:
                        messagebox.showwarning(tr("Opções"), tr('Dois jogos usam o mesmo programa ({}).').format(q['exe']), parent=win)
                        return False
                    seen.add(q["exe"].lower())
                self.settings["profiles"] = [dict(q) for q in keep]
                self.settings["auto_game"] = bool(auto_var.get())
                self._apply_profile_fields(gm_extras.find_profile(self.settings["profiles"],
                                                                  chosen["exe"]))
                return True

            def import_games():
                """Lists the Steam and Epic games found on this PC and adds the ones the person ticks."""
                commit()
                btn_imp.config(state="disabled", text=tr("Procurando jogos da Steam e da Epic..."))
                holder = []

                def scan():
                    try:
                        holder.append(gm_games.find_games())
                    except Exception:
                        holder.append([])
                    self.after_queue.put(show)

                def show():
                    btn_imp.config(state="normal", text=tr("Importar da Steam / Epic..."))
                    have = {q["exe"].lower() for q in profs if q["exe"]}
                    games = [g for g in holder[0] if g["exe"].lower() not in have]
                    if not games:
                        messagebox.showinfo(tr("Importar jogos"), tr("Não achei jogos novos da Steam ou da Epic neste PC."),
                                            parent=win)
                        return
                    dlg = tk.Toplevel(win)
                    dlg.title(tr("Importar jogos"))
                    dlg.configure(bg=BG)
                    dlg.transient(win)
                    dlg.geometry("520x440")
                    dlg.grab_set()
                    tk.Label(dlg, text=tr("Marque os jogos que quer adicionar. Cada um vira um perfil com o programa e "
                                       "o caminho já preenchidos."), bg=BG, fg=MUTED, font=(FONT, 9),
                             justify="left", wraplength=480).pack(anchor="w", padx=18, pady=(14, 8))
                    foot = tk.Frame(dlg, bg=BG)
                    foot.pack(side="bottom", fill="x", padx=18, pady=14)
                    box = tk.Frame(dlg, bg=PANEL)
                    box.pack(fill="both", expand=True, padx=18)
                    lb = tk.Listbox(box, selectmode="extended", bg=PANEL, fg=TEXT, selectbackground=ACCENT,
                                    selectforeground="#ffffff", relief="flat", bd=0, highlightthickness=0,
                                    font=(FONT, 10), activestyle="none", exportselection=False)
                    sb = ttk.Scrollbar(box, orient="vertical", command=lb.yview)
                    lb.configure(yscrollcommand=sb.set)
                    lb.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
                    sb.pack(side="right", fill="y")
                    for g in games:
                        lb.insert("end", f"[{g['source']}]  {g['name']}  ({g['exe']})")

                    def add_selected():
                        picked = [games[i] for i in lb.curselection()]
                        for g in picked:
                            profs.append(gm_extras.new_profile(g["exe"], g["name"], path=g["path"]))
                        if picked:
                            sel[0] = len(profs) - 1
                            load()
                            messagebox.showinfo(tr("Importar jogos"), tr("{} jogo(s) adicionado(s). Clique em Salvar "
                                                                      "para guardar.").format(len(picked)),
                                                parent=dlg)
                        dlg.destroy()

                    tk.Button(foot, text=tr("Adicionar selecionados"), command=add_selected, bg=ACCENT, fg="white",
                              activebackground=ACCENT_HOVER, activeforeground="white", relief="flat", bd=0,
                              padx=18, pady=7, font=(FONT, 9, "bold"), cursor="hand2").pack(side="right")
                    tk.Button(foot, text=tr("Fechar"), command=dlg.destroy, bg=PANEL, fg=TEXT,
                              activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0,
                              padx=18, pady=7, font=(FONT, 9), cursor="hand2").pack(side="right", padx=8)
                    tk.Button(foot, text=tr("Marcar todos"), command=lambda: lb.selection_set(0, "end"), bg=BG,
                              fg=MUTED, activebackground=BG, activeforeground=TEXT, relief="flat", bd=0,
                              font=(FONT, 9), cursor="hand2").pack(side="left")

                threading.Thread(target=scan, daemon=True).start()

            if btn_imp is not None:
                btn_imp.config(command=import_games)
            prof_pick.bind("<<ComboboxSelected>>", pick)
            btn_new.config(command=add_profile)
            btn_del.config(command=remove_profile)
            load()

        if gm_extras is not None:
            label(tr("Atualizações"), pady=(16, 4))
            upd_names = dict(UPDATE_MODE_LABELS)
            upd_var = tk.StringVar(value=upd_names.get(self.settings["updates"]["mode"], upd_names["ask"]))
            ttk.Combobox(body, textvariable=upd_var, values=[t for _k, t in UPDATE_MODE_LABELS],
                         state="readonly", font=(FONT, 10)).pack(fill="x", padx=20, ipady=3)
            upd_row = tk.Frame(body, bg=BG)
            upd_row.pack(fill="x", padx=20, pady=(8, 0))
            upd_label = tk.Label(body, text="" if is_frozen() else
                                 tr("Rodando como script: a atualização automática só vale no programa "
                                 "instalado (.exe)."), bg=BG, fg=MUTED, font=(FONT, 8), justify="left",
                                 wraplength=520)
            tk.Button(upd_row, text=tr("Procurar atualização agora"), relief="flat", bd=0, bg=PANEL, fg=TEXT,
                      activebackground=BORDER, activeforeground=TEXT, padx=12, pady=5, font=(FONT, 9),
                      cursor="hand2", command=lambda: self._upd_check(True, upd_label)).pack(side="left")
            upd_label.pack(anchor="w", padx=20, pady=(4, 0))

        label(tr("Ao abrir o programa"))
        try:
            at_login = autostart_enabled()
        except Exception:
            at_login = False
        start_vars = {
            "autostart_mode": tk.BooleanVar(value=self.settings["autostart_mode"]),
            "start_minimized": tk.BooleanVar(value=self.settings["start_minimized"]),
        }
        login_var = tk.BooleanVar(value=at_login)
        check(tr("Ligar o Game Mode automaticamente"), start_vars["autostart_mode"])
        check(tr("Abrir minimizado"), start_vars["start_minimized"])
        check(tr("Abrir junto com o Windows (só para o seu usuário)"), login_var)

        label(tr("O que fazer"))
        checks = [
            ("high", tr("Prioridade ALTA no jogo (padrão: acima do normal)")),
            ("eco", tr("Modo de eficiência nos apps em segundo plano")),
            ("mem_priority", tr("Prioridade de memória baixa nos apps em segundo plano")),
            ("trim", tr("Liberar memória dos apps em segundo plano")),
            ("trim_all", tr("Liberar memória de todos os apps (não só os da lista)")),
            ("retrim", tr("Repetir a liberação de memória a cada 60 segundos")),
            ("unslow_active", tr("App da lista que você está usando volta ao normal até você sair dele")),
            ("io_priority", tr("Disco com prioridade baixa nos apps em segundo plano")),
            ("power_plan", tr("Plano de energia Alto desempenho enquanto o jogo roda")),
            ("keep_awake", tr("Não deixar a tela apagar nem o PC dormir durante o jogo")),
            ("limit_cpu", tr("Prender os apps em segundo plano a menos núcleos (PCs com mais de 4)")),
        ]
        if gm_extras is None:
            checks.append(("gpu_pref", tr("Roblox usa a GPU de alto desempenho (preferência do Windows)")))
        vars_ = {}
        for key, text in checks:
            vars_[key] = tk.BooleanVar(value=self.settings[key])
            check(text, vars_[key])

        calm_box = AppListEditor(
            body, tr("Apps para deixar mais lentos"), self.settings["calm"], self._running_choices,
            lambda n: tr("Esse app está na lista de protegidos e nunca é tocado.")
            if n in {x.lower() for x in protect_box.get()} else None, height=6)
        calm_box.pack(fill="x", padx=20, pady=(16, 0))
        protect_box = AppListEditor(
            body, tr("Apps que nunca devem ser tocados"), self.settings["protect"],
            self._running_choices, None, height=5)
        protect_box.pack(fill="x", padx=20, pady=(16, 0))

        label(tr("Desempenho do próprio Game Mode"))
        perf_opts = [("normal", tr("Normal")), ("light", tr("Leve (usa menos processador)")),
                     ("minimal", tr("Mínimo (o mais leve)"))]
        perf_opts = [(k, tr(t)) for k, t in perf_opts]
        perf_var = tk.StringVar(value=label_of(perf_opts, self.settings["perf"].get("level", "normal")))
        prow = tk.Frame(body, bg=BG)
        prow.pack(fill="x", padx=20)
        tk.Label(prow, text=tr("Uso de processador"), bg=BG, fg=TEXT, font=(FONT, 9)).pack(side="left", padx=(0, 14))
        ttk.Combobox(prow, textvariable=perf_var, values=[t for _k, t in perf_opts], state="readonly",
                     width=30, font=(FONT, 9)).pack(side="left")
        tk.Label(body, text=tr("Leve e Mínimo olham o jogo e a tela com menos frequência: o overlay atualiza mais "
                            "devagar e o programa gasta menos processador. Use se o PC estiver no limite."),
                 bg=BG, fg=MUTED, font=(FONT, 8), justify="left", wraplength=470).pack(anchor="w", padx=20,
                                                                                         pady=(4, 6))
        start_vars["sounds"] = tk.BooleanVar(value=self.settings["sounds"])
        start_vars["update_notice"] = tk.BooleanVar(value=self.settings["update_notice"])
        check(tr("Bipe ao ligar e desligar o Game Mode"), start_vars["sounds"])
        check(tr("Avisar quando o Game Mode for atualizado"), start_vars["update_notice"])

        label(tr("Acessibilidade"))
        lang_opts = [("auto", tr("Automático (igual ao Windows)")), ("en", "English"),
                     ("pt", "Português"), ("es", "Español")]
        theme_opts = [("auto", tr("Automático (igual ao Windows)")), ("dark", tr("Tema escuro")),
                      ("light", tr("Tema claro"))]
        cur_lang, cur_theme = gm_i18n.choices() if gm_i18n is not None else ("auto", "dark")
        lang_var = tk.StringVar(value=label_of(lang_opts, cur_lang))
        theme_var = tk.StringVar(value=label_of(theme_opts, cur_theme))
        acc = tk.Frame(body, bg=BG)
        acc.pack(fill="x", padx=20)
        for i, (text, var, opts) in enumerate(((tr("Idioma"), lang_var, lang_opts),
                                               (tr("Tema"), theme_var, theme_opts))):
            tk.Label(acc, text=text, bg=BG, fg=TEXT, font=(FONT, 9)).grid(row=i, column=0, sticky="w",
                                                                        pady=3, padx=(0, 14))
            ttk.Combobox(acc, textvariable=var, values=[t for _k, t in opts], state="readonly", width=30,
                         font=(FONT, 9)).grid(row=i, column=1, sticky="w", pady=3)
        tk.Label(body, text=tr("O idioma e o tema só mudam depois de reiniciar o Game Mode."), bg=BG, fg=MUTED,
                 font=(FONT, 8)).pack(anchor="w", padx=20, pady=(4, 0))

        label(tr("Ferramentas"))
        tools = tk.Frame(body, bg=BG)
        tools.pack(fill="x", padx=20)
        for text, command in ((tr("Copiar diagnóstico"), self.copy_diagnostics),
                              (tr("Abrir pasta dos dados"), self.open_data_folder)):
            tk.Button(tools, text=text, command=command, relief="flat", bd=0, bg=PANEL, fg=TEXT,
                      activebackground=BORDER, activeforeground=TEXT, padx=14, pady=6,
                      font=(FONT, 9), cursor="hand2").pack(side="left", padx=(0, 8))
        tk.Label(body, text=tr('Versão {}').format(APP_VERSION), bg=BG, fg=MUTED, font=(FONT, 8)).pack(
            anchor="w", padx=20, pady=(10, 14))

        def save():
            game = game_var.get().strip()
            if not game:
                messagebox.showwarning(tr("Opções"), tr("Escolha ou digite o programa do jogo."), parent=win)
                return
            if not game.lower().endswith(".exe"):
                game += ".exe"
            if gm_extras is not None:
                if not apply_profiles():
                    return
                game = self.settings["game"]
                self.settings["updates"]["mode"] = {t: k for k, t in UPDATE_MODE_LABELS}.get(
                    upd_var.get(), "ask")
            self.settings["game"] = game
            for key, var in vars_.items():
                self.settings[key] = bool(var.get())
            for key, var in start_vars.items():
                self.settings[key] = bool(var.get())
            self.settings["protect"] = sorted(set(protect_box.get()))
            self.settings["calm"] = sorted(set(calm_box.get()) - set(self.settings["protect"]))
            if bool(login_var.get()) != at_login:
                ok, err = set_autostart(bool(login_var.get()))
                if not ok:
                    messagebox.showwarning(
                        tr("Opções"), tr("Não consegui mudar o início com o Windows:\n") + err, parent=win)
            self.settings["perf"] = {"level": key_of(perf_opts, perf_var.get())}
            set_perf(self.settings["perf"]["level"])
            self._apply_gpu_pref()
            new_lang, new_theme = key_of(lang_opts, lang_var.get()), key_of(theme_opts, theme_var.get())
            ui_changed = (new_lang, new_theme) != (cur_lang, cur_theme)
            self.settings["ui"] = {"lang": new_lang, "theme": new_theme}
            save_settings(self.settings)
            win.destroy()
            if ui_changed and messagebox.askyesno(
                    "Game Mode", tr("Para aplicar o idioma e o tema, o Game Mode precisa reiniciar. "
                                    "Reiniciar agora?"), parent=self.root):
                self._restart_program()
                return
            if self.is_on():  # reinicia com as novas opções
                self.engine.stop()
                self.stopping = True
                self.pending_restart = True

        def reset():
            if gm_extras is not None:
                profs[:] = [dict(q) for q in DEFAULT_SETTINGS["profiles"]]
                sel[0] = 0
                auto_var.set(DEFAULT_SETTINGS["auto_game"])
                load()
            game_var.set(DEFAULT_SETTINGS["game"])
            for key, var in vars_.items():
                var.set(DEFAULT_SETTINGS[key])
            for key, var in start_vars.items():
                var.set(DEFAULT_SETTINGS[key])
            perf_var.set(label_of(perf_opts, "normal"))
            calm_box.set(DEFAULT_SETTINGS["calm"])
            protect_box.set(DEFAULT_SETTINGS["protect"])

        tk.Button(bar, text=tr("Salvar"), command=save, bg=ACCENT, fg="white",
                  activebackground=ACCENT_HOVER, activeforeground="white", relief="flat", bd=0,
                  padx=22, pady=7, font=(FONT, 9, "bold"), cursor="hand2").pack(side="right")
        tk.Button(bar, text=tr("Cancelar"), command=win.destroy, bg=PANEL, fg=TEXT,
                  activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0,
                  padx=18, pady=7, font=(FONT, 9), cursor="hand2").pack(side="right", padx=8)
        tk.Button(bar, text=tr("Restaurar padrões"), command=reset, bg=BG, fg=MUTED,
                  activebackground=BG, activeforeground=TEXT, relief="flat", bd=0,
                  font=(FONT, 9), cursor="hand2").pack(side="left")

    def _restart_program(self):
        """Closes everything cleanly and opens the program again (used after a language/theme change)."""
        args = [sys.executable] + ([] if is_frozen() else [os.path.abspath(sys.argv[0])])
        args += [x for x in sys.argv[1:] if x not in ("--admin-job", "--minimized")]
        self.on_close()
        try:
            subprocess.Popen(args, close_fds=True, creationflags=0x00000008)   # DETACHED_PROCESS
        except OSError:
            pass

    # ---- fechar ------------------------------------------------------

    def on_close(self):
        """Solta teclas e botões, restaura o Game Mode e salva as configurações."""
        try:
            if self.move:
                self.move.stop()
            self._remember_window()
            self._save()
            if gm_extras is not None and self._pt is not None:
                gm_extras.save_playtime(PLAYTIME_PATH, self._pt)
        except Exception:
            pass
        self._auto_stop.set()
        try:
            self.overlay.hide()
            self.hud.hide()
            self.hud_stats.stop()
            self.hud_input.stop()
            shader_clear()
            restore_brightness()  # a tela volta ao normal ao fechar
        except Exception:
            pass
        if self.engine is not None and self.engine.is_alive():
            self.engine.stop()
            self.engine.join(timeout=6)  # restaura tudo antes de sair
        self.root.destroy()


def main():
    _detach_console()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root, start_minimized="--minimized" in sys.argv)
    root.mainloop()


def run_main():
    if "--admin-job" in sys.argv:        # processo elevado: faz a tarefa fixa e sai, sem janela
        os._exit(admin_job_main(sys.argv))
    try:
        main()
    except Exception:
        details = traceback.format_exc()
        write_error_log(details)
        try:
            messagebox.showerror("Game Mode", tr("Ocorreu um erro ao iniciar:\n\n") + details[-1500:])
        except Exception:
            pass


if __name__ == "__main__":
    run_main()
