"""Text insertion on Windows: save clipboard, set text, synthesize Ctrl+V, restore.

Mirrors the macOS paste module's Wispr-style flow (save, set, paste, restore)
using the Win32 clipboard and SendInput for the Ctrl+V keystroke. ctypes only
— no pywin32 dependency required — so the module also works in a stock CPython
environment.
"""

import ctypes
import time
from ctypes import wintypes

# Win32 constants we use; names mirror the SDK headers for grep-ability.
_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002
_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_VK_CONTROL = 0x11
_VK_V = 0x56


# --- clipboard ---------------------------------------------------------------

# Win32 handles (HGLOBAL, void*) need correct ctypes signatures. Letting
# ctypes default to returning c_int truncates 64-bit pointers on Windows,
# which produces non-zero alloc handles but null GlobalLock results.
_kernel32 = ctypes.windll.kernel32
_user32 = ctypes.windll.user32

_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
_kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
_kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)

_user32.OpenClipboard.argtypes = (wintypes.HWND,)
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.CloseClipboard.argtypes = ()
_user32.CloseClipboard.restype = wintypes.BOOL
_user32.EmptyClipboard.argtypes = ()
_user32.EmptyClipboard.restype = wintypes.BOOL
_user32.IsClipboardFormatAvailable.argtypes = (wintypes.UINT,)
_user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
_user32.GetClipboardData.argtypes = (wintypes.UINT,)
_user32.GetClipboardData.restype = wintypes.HANDLE
_user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
_user32.SetClipboardData.restype = wintypes.HANDLE


def _open_clipboard() -> None:
    # retry briefly: another process may have the clipboard open
    for _ in range(20):
        if _user32.OpenClipboard(0):
            return
        time.sleep(0.05)
    raise OSError("OpenClipboard failed; another process holds the clipboard")


def _get_clipboard_text() -> str | None:
    if not _user32.IsClipboardFormatAvailable(_CF_UNICODETEXT):
        return None
    handle = _user32.GetClipboardData(_CF_UNICODETEXT)
    if not handle:
        return None
    ptr = _kernel32.GlobalLock(handle)
    if not ptr:
        return None
    try:
        # wide-char string, null-terminated
        length = 0
        while ctypes.cast(ptr + length * 2, ctypes.POINTER(wintypes.WCHAR))[0]:
            length += 1
        return ctypes.wstring_at(ptr, length)
    finally:
        _kernel32.GlobalUnlock(handle)


def _set_clipboard_text(text: str) -> None:
    _user32.EmptyClipboard()

    data = text.encode("utf-16-le") + b"\x00\x00"
    size = len(data)
    handle = _kernel32.GlobalAlloc(_GMEM_MOVEABLE, size)
    if not handle:
        raise OSError("GlobalAlloc failed")
    ptr = _kernel32.GlobalLock(handle)
    if not ptr:
        _kernel32.GlobalFree(handle)
        raise OSError("GlobalLock failed")
    try:
        ctypes.memmove(ptr, data, size)
    finally:
        _kernel32.GlobalUnlock(handle)
    if not _user32.SetClipboardData(_CF_UNICODETEXT, handle):
        _kernel32.GlobalFree(handle)
        raise OSError("SetClipboardData failed")
    # ownership transfers to the system after SetClipboardData; do not GlobalFree.


# --- synthesized Ctrl+V ------------------------------------------------------

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    )


class _INPUT(ctypes.Structure):
    class _UNION(ctypes.Union):
        _fields_ = (("ki", _KEYBDINPUT), ("padding", ctypes.c_byte * 64))

    _anonymous_ = ("u",)
    _fields_ = (
        ("type", wintypes.DWORD),
        ("u", _UNION),
    )


def _send_ctrl_v() -> None:
    user32 = ctypes.windll.user32
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT

    inputs = (_INPUT * 2)()
    # key down: Ctrl + V
    inputs[0].type = _INPUT_KEYBOARD
    inputs[0].ki.wVk = _VK_CONTROL
    inputs[0].ki.dwFlags = 0
    inputs[1].type = _INPUT_KEYBOARD
    inputs[1].ki.wVk = _VK_V
    inputs[1].ki.dwFlags = 0
    # key up: V then Ctrl (release order matches hardware behaviour)
    release = (_INPUT * 2)()
    release[0].type = _INPUT_KEYBOARD
    release[0].ki.wVk = _VK_V
    release[0].ki.dwFlags = _KEYEVENTF_KEYUP
    release[1].type = _INPUT_KEYBOARD
    release[1].ki.wVk = _VK_CONTROL
    release[1].ki.dwFlags = _KEYEVENTF_KEYUP

    user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(_INPUT))
    user32.SendInput(2, ctypes.byref(release), ctypes.sizeof(_INPUT))


# --- public API (matches accio.paste) ---------------------------------------

def paste_text(text: str, restore_delay: float = 0.3) -> None:
    _open_clipboard()
    try:
        previous = _get_clipboard_text()
        _set_clipboard_text(text)
    finally:
        ctypes.windll.user32.CloseClipboard()

    time.sleep(0.05)  # let the clipboard settle before the paste keystroke
    _send_ctrl_v()
    time.sleep(restore_delay)  # target app must read the clipboard before restore

    _open_clipboard()
    try:
        if previous is not None:
            _set_clipboard_text(previous)
    finally:
        ctypes.windll.user32.CloseClipboard()


def copy_only(text: str) -> None:
    _open_clipboard()
    try:
        _set_clipboard_text(text)
    finally:
        ctypes.windll.user32.CloseClipboard()
