from __future__ import annotations
import ctypes
import ctypes.wintypes as wintypes
from PySide6 import QtCore

# -------- Global hotkey (RegisterHotKey) --------
user32 = ctypes.windll.user32
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
VK_MAP = {chr(i): i for i in range(0x41, 0x5B)}


class HotkeyFilter(QtCore.QObject, QtCore.QAbstractNativeEventFilter):
    hotkeyPressed = QtCore.Signal()

    def __init__(self, hotkey_id: int):
        super().__init__()
        self.hotkey_id = hotkey_id

    def nativeEventFilter(self, eventType, message):
        try:
            # Qt may use either "windows_generic_MSG" or "windows_dispatcher_MSG".
            if eventType not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
                return False, 0
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                self.hotkeyPressed.emit()
                return True, 0
            return False, 0
        except Exception:
            return False, 0


def register_hotkey(hotkey_id: int, ctrl: bool, alt: bool, shift: bool, vk_letter: str) -> bool:
    mods = 0
    if ctrl:
        mods |= MOD_CONTROL
    if alt:
        mods |= MOD_ALT
    if shift:
        mods |= MOD_SHIFT
    vk = VK_MAP.get(vk_letter.upper(), VK_MAP["S"])
    return bool(user32.RegisterHotKey(None, hotkey_id, mods, vk))


def unregister_hotkey(hotkey_id: int) -> None:
    try:
        user32.UnregisterHotKey(None, hotkey_id)
    except Exception:
        pass
