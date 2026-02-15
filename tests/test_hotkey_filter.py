from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes

from PySide6 import QtCore, QtWidgets

from ctxsnap.ui.hotkey import HotkeyFilter, WM_HOTKEY


def test_hotkey_filter_emits_signal_on_wm_hotkey() -> None:
    # Signals can work without an event loop, but ensure the Qt application exists.
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])

    hotkey_id = 0x1234
    f = HotkeyFilter(hotkey_id)
    triggered: list[bool] = []
    f.hotkeyPressed.connect(lambda: triggered.append(True))

    msg = wintypes.MSG()
    msg.message = WM_HOTKEY
    msg.wParam = hotkey_id

    handled, _ = f.nativeEventFilter("windows_generic_MSG", ctypes.addressof(msg))
    assert handled is True
    assert triggered == [True]
