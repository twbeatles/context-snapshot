## CtxSnap GPT Notes

### Project summary
- CtxSnap is a PySide6 Windows app that captures and restores working context snapshots.
- Each snapshot can include root folder, note, TODOs, tags, recent files, filtered processes, and running apps.
- Data is stored under `%APPDATA%\ctxsnap\` as JSON (snapshots, index, settings, logs).

### Repository layout
- `ctxsnap_win.py`: main application entry point, UI, settings dialogs, and restore flows.
- `ctxsnap/utils.py`: helper utilities for recent-file scanning, process/app collection, search indexing, and restore helpers.
- `ctxsnap/`: package for shared modules (currently `utils.py` and `storage.py`).
- `README.md`: user-facing documentation.
- `requirements.txt`: Python dependencies.
- `ctxsnap_win.spec`: PyInstaller spec.
- `installer/`: Inno Setup installer scripts.
- `assets/`: icons/images used by the app.

### Data files and storage
- `%APPDATA%\\ctxsnap\\snapshots\\<id>.json`: snapshot payloads.
- `%APPDATA%\\ctxsnap\\index.json`: list/index metadata (includes search blob cache).
- `%APPDATA%\\ctxsnap\\settings.json`: app settings.
- `%APPDATA%\\ctxsnap\\restore_history.json`: restore history log.
- `%APPDATA%\\ctxsnap\\logs\\ctxsnap.log`: rotating log file.

### Core flows
- **Snapshot creation**: `MainWindow._create_snapshot()` builds `Snapshot` data and writes it to disk; index metadata is updated in `save_snapshot()`.
- **Restore**: `MainWindow._restore_by_id()` applies selected restore options, triggers running-app restore, and logs restore history.
- **Search/filter**: `MainWindow.refresh_list()` filters by query, tags, pinned, date range, and uses cached search blobs.

### Settings and defaults
- `migrate_settings()` and `ensure_storage()` define defaults and backfill new keys.
- Capture toggles exist for recent files, processes, and running apps.
- Recent-file scan limits and exclude patterns are configurable.
- Auto snapshot: interval minutes and git-change triggers.
- Restore defaults: folder/terminal/VSCode/running apps and post-restore checklist.

### Automation & integrations
- Auto snapshot timer uses `QTimer` and respects `auto_snapshot_minutes`.
- Git change detection uses `git_state()` with a periodic timer.
- Export tools include snapshot JSON and weekly report Markdown.

### Development commands
- Run dev: `pip install -r requirements.txt` then `python ctxsnap_win.py`.
- Build EXE: `python -m PyInstaller ctxsnap_win.spec`.

### Contributor notes
- Keep filesystem scans bounded (time and count).
- Avoid storing sensitive data by default; honor capture toggles.
- Prefer refactoring shared logic into `ctxsnap/utils.py`.
- Be mindful of UI responsiveness when adding heavy operations.
