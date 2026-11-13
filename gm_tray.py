"""Icon in the Windows notification area (next to the clock), made with ctypes only.

Left click opens the window; right click shows a small menu. The icon lives in its own thread with a
hidden window, and it tells the program what was clicked through the callbacks given to Tray().
Nothing here is needed to use the program: if anything fails, Tray.start() just returns False.
"""
import ctypes
import os
import sys
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WM_NULL, WM_DESTROY = 0x0000, 0x0002
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_CONTEXTMENU = 0x0202, 0x0203, 0x0205, 0x007B
WM_USER = 0x0400
WM_TRAY = WM_USER + 20          # what the icon sends us
WM_APP_UPDATE = WM_USER + 21    # tooltip / balloon changed
WM_APP_STOP = WM_USER + 22      # close the icon
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO = 0x1
MF_STRING, MF_SEPARATOR = 0x0, 0x800
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x2, 0x80, 0x100
IMAGE_ICON, LR_LOADFROMFILE, SM_CXSMICON = 1, 0x10, 49
CLASS_NAME = "GameModeTrayWindow"


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]


def _prototypes():
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, ctypes.c_void_p]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = ctypes.c_int
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.restype = LRESULT
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterWindowMessageW.restype = wintypes.UINT
    user32.CreatePopupMenu.restype = wintypes.HANDLE
    user32.AppendMenuW.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.TrackPopupMenu.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
    user32.TrackPopupMenu.restype = ctypes.c_int
    user32.DestroyMenu.argtypes = [wintypes.HANDLE]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int,
                                  ctypes.c_int, wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wintypes.HANDLE
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON),
                                       ctypes.POINTER(wintypes.HICON), wintypes.UINT]
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def load_icon(path):
    """The small icon from app.ico; if that file is missing, the icon of the .exe; else the default one."""
    size = user32.GetSystemMetrics(SM_CXSMICON) or 16
    if path and os.path.isfile(path):
        handle = user32.LoadImageW(None, path, IMAGE_ICON, size, size, LR_LOADFROMFILE)
        if handle:
            return handle
    small = wintypes.HICON()
    try:
        if shell32.ExtractIconExW(sys.executable, 0, None, ctypes.byref(small), 1) and small:
            return small
    except Exception:
        pass
    return user32.LoadIconW(None, ctypes.c_void_p(32512))          # IDI_APPLICATION


class Tray:
    """on_open / on_toggle / on_restore / on_exit are called from the tray thread: keep them tiny
    (the program passes functions that only hand the work to its own window thread)."""

    def __init__(self, tooltip, icon_path, labels, on_open, on_toggle, on_restore, on_exit):
        self._tip = tooltip
        self._icon_path = icon_path
        self._labels = labels                    # function returning (open, toggle, restore, exit) texts
        self._handlers = {1: on_open, 2: on_toggle, 3: on_restore, 4: on_exit}
        self._open = on_open
        self._balloon = None
        self._hicon = None
        self._taskbar_msg = 0
        self._proc = None
        self._ready = threading.Event()
        self._thread = None
        self.hwnd = None

    # ---- public (any thread)
    def start(self):
        self._thread = threading.Thread(target=self._run, name="gm-tray", daemon=True)
        self._thread.start()
        self._ready.wait(4.0)
        return bool(self.hwnd)

    def stop(self):
        hwnd, self.hwnd = self.hwnd, None
        if hwnd:
            user32.PostMessageW(hwnd, WM_APP_STOP, 0, 0)
            if self._thread is not None:
                self._thread.join(2.0)

    def set_tooltip(self, text):
        self._tip = text
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_APP_UPDATE, 0, 0)

    def notify(self, title, text):
        """A small pop-up message from the icon (Windows shows it as a notification)."""
        self._balloon = (title, text)
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_APP_UPDATE, 0, 0)

    # ---- tray thread
    def _data(self, flags):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        nid.szTip = (self._tip or "")[:127]
        return nid

    def _add(self):
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)))

    def _modify(self):
        flags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid = self._data(flags)
        if self._balloon:
            title, text = self._balloon
            self._balloon = None
            nid.uFlags = flags | NIF_INFO
            nid.szInfoTitle = title[:63]
            nid.szInfo = text[:255]
            nid.dwInfoFlags = NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _remove(self):
        try:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._data(NIF_MESSAGE)))
        except Exception:
            pass

    def _menu(self, hwnd):
        texts = list(self._labels())
        menu = user32.CreatePopupMenu()
        for index, text in enumerate(texts, start=1):
            if index == 4:
                user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, index, text)
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(hwnd)          # without this the menu would not close when you click away
        chosen = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                                       point.x, point.y, 0, hwnd, None)
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        handler = self._handlers.get(chosen)
        if handler:
            handler()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                event = lparam & 0xFFFF
                if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._open()
                elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._menu(hwnd)
                return 0
            if msg == WM_APP_UPDATE:
                self._modify()
                return 0
            if msg == WM_APP_STOP:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            if self._taskbar_msg and msg == self._taskbar_msg:    # Explorer restarted: put the icon back
                self._add()
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self):
        try:
            _prototypes()
            instance = kernel32.GetModuleHandleW(None)
            self._proc = WNDPROC(self._wndproc)           # keep a reference or Windows crashes the program
            cls = WNDCLASSW()
            cls.lpfnWndProc = self._proc
            cls.hInstance = instance
            cls.lpszClassName = CLASS_NAME
            user32.RegisterClassW(ctypes.byref(cls))      # fails harmlessly if it already exists
            hwnd = user32.CreateWindowExW(0, CLASS_NAME, "Game Mode", 0, 0, 0, 0, 0, None, None,
                                          instance, None)
            if not hwnd:
                return
            self.hwnd = hwnd
            self._taskbar_msg = user32.RegisterWindowMessageW("TaskbarCreated")
            self._hicon = load_icon(self._icon_path)
            self._add()
        except Exception:
            self.hwnd = None
            return
        finally:
            self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        self._remove()
