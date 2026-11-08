"""
gm_mods.py - Movement Helper do Game Mode (Windows).

O que faz: quando você segura duas teclas opostas juntas (esquerda+direita ou
frente+trás), decide qual vale:
  neutral = nenhuma (o personagem para naquele eixo)
  first   = a primeira que você apertou
  last    = a última que você apertou

Só mexe nas quatro teclas configuradas. Só age com o jogo em foco (se pedido).
Não grava nem guarda nada do que você digita.

Interface usada pelo gamemode_app.py:
  key_to_vk(texto) -> código da tecla ou None
  MovementHelper(keys, mode, game, only_game, notify=None)
      .start() -> (ok, mensagem)   .stop()   .running   .focus.in_game
"""

import os
import sys
import threading
import time

AXES = (("left", "right"), ("fwd", "back"))
NAMES = ("fwd", "back", "left", "right")
MODES = ("neutral", "first", "last")
MARK = 0x474D4D56  # "GMMV": marca os eventos que o próprio programa envia

_ARROWS = {
    "up": 0x26, "cima": 0x26, "\u2191": 0x26, "seta para cima": 0x26,
    "down": 0x28, "baixo": 0x28, "\u2193": 0x28, "seta para baixo": 0x28,
    "left": 0x25, "esquerda": 0x25, "\u2190": 0x25, "seta para esquerda": 0x25,
    "right": 0x27, "direita": 0x27, "\u2192": 0x27, "seta para direita": 0x27,
}
_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}


def key_to_vk(text):
    """Texto da caixa -> código virtual da tecla. None se não entendi."""
    t = (text or "").strip().lower()
    if not t:
        return None
    if t in _ARROWS:
        return _ARROWS[t]
    if len(t) == 1 and ("a" <= t <= "z" or "0" <= t <= "9"):
        return ord(t.upper())
    if t[0] == "f" and t[1:].isdigit():
        n = int(t[1:])
        if 1 <= n <= 24:
            return 0x70 + n - 1
    return None


class SocdState:
    """Lógica pura (sem Windows): teclas físicas apertadas -> teclas que o jogo deve ver."""

    def __init__(self, keys, mode):
        values = [keys[n] for n in NAMES]
        if len(set(values)) != len(values):
            raise ValueError("teclas repetidas")
        self.keys = dict(keys)
        self.mode = mode if mode in MODES else "last"
        self.vk_to_name = {keys[n]: n for n in NAMES}
        self.order = {a: [] for a in AXES}  # teclas físicas de cada eixo, na ordem do aperto

    def _axis_of(self, name):
        for axis in AXES:
            if name in axis:
                return axis

    def press(self, name):
        order = self.order[self._axis_of(name)]
        if name not in order:
            order.append(name)

    def release(self, name):
        order = self.order[self._axis_of(name)]
        if name in order:
            order.remove(name)

    def is_down(self, name):
        return name in self.order[self._axis_of(name)]

    def output(self):
        """Conjunto de nomes que devem estar apertados para o jogo."""
        out = set()
        for axis in AXES:
            order = self.order[axis]
            if len(order) == 1:
                out.add(order[0])
            elif len(order) == 2:
                if self.mode == "first":
                    out.add(order[0])
                elif self.mode == "last":
                    out.add(order[1])
        return out

    def physical(self):
        return {n for axis in AXES for n in self.order[axis]}


class Focus:
    """in_game = o helper está agindo agora (jogo em foco, ou 'só no jogo' desligado)."""

    def __init__(self):
        self.in_game = False


class MovementHelper:
    def __init__(self, keys, mode, game, only_game, notify=None):
        self.state = SocdState(keys, mode)
        self.game = (game or "").lower()
        self.only_game = bool(only_game)
        self.notify = notify or (lambda level, text: None)
        self.focus = Focus()
        self.running = False
        self._lock = threading.RLock()
        self._sent = set()       # teclas que EU deixei apertadas no Windows
        self._thread = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._error = ""
        self._hook = None
        self._proc = None
        self._stop_watch = threading.Event()
        self._api = None

    # ---------------------------------------------------------------- Windows
    def _load(self):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)

        class KBD(ctypes.Structure):
            _fields_ = [("vk", wintypes.DWORD), ("scan", wintypes.DWORD), ("flags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]

        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
        user32.CallNextHookEx.restype = LRESULT
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
        user32.PostThreadMessageW.restype = wintypes.BOOL
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
        user32.MapVirtualKeyW.restype = wintypes.UINT
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                        wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        self._api = dict(ctypes=ctypes, wintypes=wintypes, user32=user32, kernel32=kernel32,
                         HOOKPROC=HOOKPROC, KBD=KBD, INPUT=INPUT, KEYBDINPUT=KEYBDINPUT)

    def _foreground_exe(self):
        a = self._api
        ctypes, wintypes, user32, kernel32 = a["ctypes"], a["wintypes"], a["user32"], a["kernel32"]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(520)
            size = wintypes.DWORD(520)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(h)
        return ""

    def _is_game(self, exe):
        if not exe:
            return False
        if exe == self.game:
            return True
        return "roblox" in self.game and exe.startswith("roblox")

    def _send(self, vk, down):
        a = self._api
        ctypes = a["ctypes"]
        scan = a["user32"].MapVirtualKeyW(vk, 0)
        flags = 0x0008  # KEYEVENTF_SCANCODE
        if vk in _EXTENDED:
            flags |= 0x0001
        if not down:
            flags |= 0x0002
        inp = a["INPUT"]()
        inp.type = 1
        inp.u.ki = a["KEYBDINPUT"](0, scan, flags, 0, MARK)
        a["user32"].SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _sync(self, target):
        """Deixa o Windows com exatamente as teclas de 'target' apertadas."""
        for name in NAMES:
            vk = self.state.keys[name]
            if name in target and name not in self._sent:
                self._send(vk, True)
                self._sent.add(name)
            elif name not in target and name in self._sent:
                self._send(vk, False)
                self._sent.discard(name)

    def _active(self):
        return self.focus.in_game

    def _hook_proc(self, n_code, w_param, l_param):
        a = self._api
        try:
            if n_code == 0:
                info = a["ctypes"].cast(l_param, a["ctypes"].POINTER(a["KBD"])).contents
                if info.extra != MARK:
                    name = self.state.vk_to_name.get(info.vk)
                    if name is not None:
                        with self._lock:
                            down = w_param in (0x0100, 0x0104)  # WM_KEYDOWN / WM_SYSKEYDOWN
                            if self._active():
                                if down:
                                    self.state.press(name)
                                else:
                                    self.state.release(name)
                                self._sync(self.state.output())
                                return 1  # engole a tecla física; o jogo vê a minha
                            # fora do jogo: só acompanha, deixa passar sem mexer
                            if down:
                                self.state.press(name)
                            else:
                                self.state.release(name)
        except Exception:
            pass
        return a["user32"].CallNextHookEx(self._hook, n_code, w_param, l_param)

    def _watch(self):
        last = None
        while not self._stop_watch.wait(0.1):
            try:
                active = (not self.only_game) or self._is_game(self._foreground_exe())
            except Exception:
                active = False
            if active != last:
                last = active
                with self._lock:
                    self.focus.in_game = active
                    if active:
                        self._sync(self.state.output())
                    else:
                        # saiu do jogo: o Windows volta a ver exatamente o que está apertado de verdade
                        self._sync(self.state.physical())

    def _run(self):
        a = self._api
        ctypes, wintypes, user32, kernel32 = a["ctypes"], a["wintypes"], a["user32"], a["kernel32"]
        self._thread_id = kernel32.GetCurrentThreadId()
        self._proc = a["HOOKPROC"](self._hook_proc)  # guardar: se o Python apagar, trava
        self._hook = user32.SetWindowsHookExW(13, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not self._hook:
            self._error = f"o Windows recusou o gancho do teclado (erro {ctypes.get_last_error()})"
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    # ------------------------------------------------------------------- API
    def start(self):
        if self.running:
            return True, ""
        if sys.platform != "win32":
            return False, "O Movement Helper só funciona no Windows."
        try:
            self._load()
            user32 = self._api["user32"]
            # começa sabendo quais das quatro teclas já estão apertadas
            for name in NAMES:
                if user32.GetAsyncKeyState(self.state.keys[name]) & 0x8000:
                    self.state.press(name)
            self._ready.clear()
            self._error = ""
            self._stop_watch.clear()
            self._thread = threading.Thread(target=self._run, name="gm-move-hook", daemon=True)
            self._thread.start()
            if not self._ready.wait(3):
                return False, "o gancho do teclado não respondeu a tempo."
            if self._error:
                return False, f"Não consegui ligar: {self._error}"
            self.running = True
            threading.Thread(target=self._watch, name="gm-move-focus", daemon=True).start()
            self.notify("ok", "Movement Helper ligado.")
            return True, ""
        except Exception as exc:
            self._cleanup()
            return False, f"Não consegui ligar: {exc}"

    def _cleanup(self):
        self._stop_watch.set()
        if self._api and self._thread_id:
            try:
                self._api["user32"].PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass
        if self._thread:
            self._thread.join(1.5)
        with self._lock:
            self.focus.in_game = False
            if self._api:
                try:
                    self._sync(self.state.physical())  # não deixa tecla "presa" no Windows
                except Exception:
                    pass
            self._sent.clear()

    def stop(self):
        if not self.running and not self._thread:
            return
        self.running = False
        self._cleanup()
        self._thread = None
        self._thread_id = 0
        self.notify("info", "Movement Helper desligado.")
