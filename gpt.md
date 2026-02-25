## CtxSnap GPT Notes

### Project summary
- CtxSnap is a PySide6 Windows app that captures and restores working context snapshots.
- Snapshots can include root folder, note, TODOs, tags, recent files, filtered processes, and running apps.
- Data is stored as JSON under `%APPDATA%\ctxsnap\`.

### Repository layout
- `ctxsnap_win.py`: app entrypoint, tray, hotkey initialization.
- `ctxsnap/app_storage.py`: storage paths, JSON IO, migrations, backup import/export.
- `ctxsnap/ui/main_window.py`: main UI and core flows (create/edit/restore/import/automation).
- `ctxsnap/ui/dialogs/*.py`: settings/snapshot/restore/history/onboarding dialogs.
- `ctxsnap/utils.py`: scanning/process/git/search helpers.
- `ctxsnap_win.spec`: PyInstaller spec for Windows build.

### Data files
- `%APPDATA%\\ctxsnap\\snapshots\\<id>.json`: full snapshot payloads.
- `%APPDATA%\\ctxsnap\\index.json`: list metadata/search cache.
- `%APPDATA%\\ctxsnap\\settings.json`: app settings.
- `%APPDATA%\\ctxsnap\\restore_history.json`: restore history entries.
- `%APPDATA%\\ctxsnap\\logs\\ctxsnap.log`: rotating logs.

### Snapshot metadata (important)
- New fields used by automation/dedup:
  - `source` (`auto_timer`, `auto_git`, etc.)
  - `trigger` (`timer`, `git_change`, etc.)
  - `git_state` (`branch`, `sha`)
  - `auto_fingerprint` (dedup hash)

### Current behavior notes
- Auto snapshot is headless (no dialog), and skips creating duplicates when fingerprint is unchanged.
- Window close (X) minimizes to tray; full exit is tray menu `Quit`.
- Backup import:
  - `Apply now` applies immediately.
  - `Keep in dialog` applies on dialog Save.
- Restore default for `open_running_apps` is `false` for new installs.
- Restore history records `running_apps_failed_count` for accurate UI display.

### Reliability constraints
- JSON writes use atomic replace in storage layer.
- Main snapshot/index/settings update paths include rollback logic on partial failure.
- Import flow takes safety backup before destructive operations and rolls back on failure.

### Build and run
- Run dev: `pip install -r requirements.txt` then `python ctxsnap_win.py`.
- Build EXE: `python -m PyInstaller ctxsnap_win.spec`.

### Contributor guidance
- Keep file scans bounded (`scan_limit`, `scan_seconds`).
- Respect capture/privacy toggles.
- Avoid UI blocking; heavy work should be backgrounded.
