from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ctxsnap.app_storage import (
    app_dir,
    ensure_storage,
    load_json,
    migrate_settings,
    save_json,
)
from ctxsnap.constants import APP_NAME
from ctxsnap.core.logging import setup_logging, get_logger
from ctxsnap.i18n import set_language, tr
from ctxsnap.restore import open_folder
from ctxsnap.ui.dialogs.onboarding import OnboardingDialog
from ctxsnap.ui.hotkey import HotkeyFilter, register_hotkey, unregister_hotkey
from ctxsnap.ui.main_window import MainWindow
from ctxsnap.ui.styles import set_pretty_style, APP_QSS
from ctxsnap.utils import log_exc, resource_path

# -------- Logging --------
LOGGER = get_logger()


def build_tray(app: QtWidgets.QApplication, win: MainWindow) -> QtWidgets.QSystemTrayIcon:
    tray = QtWidgets.QSystemTrayIcon(win)
    icon = app.windowIcon()
    tray.setIcon(icon)
    tray.setToolTip("CtxSnap")

    menu = QtWidgets.QMenu()

    act_quick = menu.addAction(f"{tr('Quick Snapshot')} ({win.hotkey_label()})")
    act_restore_last = menu.addAction(tr("Restore Last"))
    menu.addSeparator()
    act_settings = menu.addAction(tr("Settings"))
    act_onboarding = menu.addAction(tr("Onboarding"))
    act_open_folder = menu.addAction(tr("Open App Folder"))
    menu.addSeparator()
    act_show = menu.addAction(tr("Show/Hide"))
    act_quit = menu.addAction(tr("Quit"))

    act_quick.triggered.connect(win.quick_snapshot)
    act_restore_last.triggered.connect(win.restore_last)
    act_settings.triggered.connect(win.open_settings)
    act_onboarding.triggered.connect(win.show_onboarding)
    act_open_folder.triggered.connect(lambda: open_folder(app_dir()))

    def toggle_show():
        if win.isVisible():
            win.hide()
        else:
            win.show()
            win.raise_()
            win.activateWindow()

    act_show.triggered.connect(toggle_show)
    act_quit.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    # keep references for live updates
    tray.act_quick = act_quick  # type: ignore[attr-defined]
    tray.activated.connect(lambda reason: toggle_show() if reason == QtWidgets.QSystemTrayIcon.Trigger else None)
    tray.show()
    return tray


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    set_pretty_style(app)
    app.setStyleSheet(APP_QSS)

    # Logging
    log_file = setup_logging()
    LOGGER.info("Starting CtxSnap (log: %s)", log_file)

    # App icon (.ico) if present
    icon_path = resource_path("assets/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    else:
        app.setWindowIcon(app.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))

    _, _, settings_path = ensure_storage()
    settings = migrate_settings(load_json(settings_path))
    save_json(settings_path, settings)

    set_language(settings.get("language"))
    win = MainWindow()
    win.show()

    # First-run onboarding (in-app guide)
    if not bool(win.settings.get("onboarding_shown", False)):
        dlg = OnboardingDialog(win)
        dlg.exec()
        win.settings["onboarding_shown"] = True
        save_json(win.settings_path, win.settings)

        # Keep menu/hotkey label consistent after onboarding
        win._build_menus()
        if hasattr(win, "btn_quick"):
            win.btn_quick.setText(f"Quick Snapshot ({win.hotkey_label()})")

    tray = build_tray(app, win)

    # Global hotkey (re-applied when settings change)
    hotkey_id = 0xC7A5
    hotkey_filter = HotkeyFilter(hotkey_id)

    QtCore.QCoreApplication.instance().installNativeEventFilter(hotkey_filter)
    hotkey_filter.hotkeyPressed.connect(win.quick_snapshot)

    def apply_hotkey_from_settings():
        unregister_hotkey(hotkey_id)
        hk = migrate_settings(win.settings).get("hotkey", {})
        if not hk.get("enabled", True):
            win.statusBar().showMessage("Hotkey disabled.", 2500)
            return
        ok = register_hotkey(
            hotkey_id,
            bool(hk.get("ctrl", True)),
            bool(hk.get("alt", True)),
            bool(hk.get("shift", False)),
            str(hk.get("vk", "S")),
        )
        if ok:
            mods = "+".join([m for m, on in [("Ctrl", hk.get("ctrl", True)), ("Alt", hk.get("alt", True)), ("Shift", hk.get("shift", False))] if on])
            win.statusBar().showMessage(f"{tr('Hotkey enabled')}: {mods}+{hk.get('vk','S')}", 3500)
        else:
            win.statusBar().showMessage(tr("Hotkey failed"), 6000)

            # Conflict handling: offer alternatives
            try:
                dlg = QtWidgets.QMessageBox(win)
                dlg.setWindowTitle(tr("Hotkey conflict"))
                dlg.setText(tr("Hotkey conflict msg"))
                dlg.setInformativeText(tr("Hotkey conflict info"))
                btn_try = dlg.addButton(tr("Try alternatives"), QtWidgets.QMessageBox.AcceptRole)
                btn_disable = dlg.addButton(tr("Disable hotkey"), QtWidgets.QMessageBox.DestructiveRole)
                dlg.addButton(tr("Keep as is"), QtWidgets.QMessageBox.RejectRole)
                dlg.exec()
                if dlg.clickedButton() == btn_try:
                    candidates = [
                        {"ctrl": True, "alt": True, "shift": False, "vk": "S"},
                        {"ctrl": True, "alt": True, "shift": False, "vk": "D"},
                        {"ctrl": True, "alt": True, "shift": False, "vk": "Q"},
                        {"ctrl": True, "alt": False, "shift": True, "vk": "S"},
                    ]
                    for cand in candidates:
                        unregister_hotkey(hotkey_id)
                        if register_hotkey(hotkey_id, cand["ctrl"], cand["alt"], cand["shift"], cand["vk"]):
                            win.settings.setdefault("hotkey", {})
                            win.settings["hotkey"].update({"enabled": True, **cand})
                            save_json(win.settings_path, win.settings)
                            win.statusBar().showMessage(f"{tr('Hotkey updated to')} {win.hotkey_label()}", 4500)
                            break
                elif dlg.clickedButton() == btn_disable:
                    win.settings.setdefault("hotkey", {})
                    win.settings["hotkey"].update({"enabled": False})
                    save_json(win.settings_path, win.settings)
                    unregister_hotkey(hotkey_id)
                    win.statusBar().showMessage(tr("Hotkey disabled"), 3500)
            except Exception as e:
                log_exc("hotkey conflict dialog", e)

        # Update UI labels that depend on hotkey
        win._build_menus()
        if hasattr(win, "btn_quick"):
            win.btn_quick.setText(f"Quick Snapshot ({win.hotkey_label()})")
        if hasattr(tray, "act_quick"):
            tray.act_quick.setText(f"Quick Snapshot ({win.hotkey_label()})")  # type: ignore[attr-defined]

    win.on_settings_applied = apply_hotkey_from_settings
    apply_hotkey_from_settings()

    def cleanup():
        tray.hide()
        unregister_hotkey(hotkey_id)

    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
