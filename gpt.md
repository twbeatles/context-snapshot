## CtxSnap GPT Notes

### Project summary
- Windows-only PySide6 app for capturing/restoring working context snapshots.
- Current architecture is service-oriented with split MainWindow sections.
- Data is stored under `%APPDATA%\\ctxsnap\\` with schema versioning and migration.

### Key modules
- `ctxsnap/app_storage.py`: storage paths, migrations, atomic JSON IO, backup import/export.
- `ctxsnap/services/*`: snapshot/restore/backup/search business services.
- `ctxsnap/core/security.py`: DPAPI envelope encryption for sensitive snapshot fields.
- `ctxsnap/core/sync/*`: sync provider protocol, sync engine, local/cloud-stub providers.
- `ctxsnap/ui/main_window.py`: orchestration only.
- `ctxsnap/ui/main_window_sections/*`: functional slices (`automation`, `list_view`, `snapshot_crud`, `settings_backup`, `restore_actions`).

### Data files
- `%APPDATA%\\ctxsnap\\snapshots\\<id>.json`
- `%APPDATA%\\ctxsnap\\index.json`
- `%APPDATA%\\ctxsnap\\settings.json`
- `%APPDATA%\\ctxsnap\\restore_history.json`
- `%APPDATA%\\ctxsnap\\sync_conflicts.json`
- `%APPDATA%\\ctxsnap\\sync_state.json`
- `%APPDATA%\\ctxsnap\\logs\\ctxsnap.log`

### Important schema bits
- `settings.schema_version = 2`
- `snapshot.schema_version = 2`
- Revision metadata: `rev`, `updated_at`
- Extended git snapshot state: `dirty`, `changed`, `staged`, `untracked`
- DPAPI envelope shape: `{\"enc\":\"dpapi\",\"v\":1,\"blob\":\"<base64>\"}`

### Feature flags (`settings.dev_flags`)
- `sync_enabled`
- `security_enabled`
- `advanced_search_enabled`
- `restore_profiles_enabled`

### Current behavior notes
- Sync conflict policy: latest wins by `(rev, updated_at)`, ambiguous conflict goes to queue.
- Field query search supports `tag:`, `root:`, `todo:` (+ aliases).
- Backup import has rollback and safety backup path.
- Close (X) minimizes to tray; full exit from tray `Quit`.

### Build / test
- Run app: `python ctxsnap_win.py`
- Test: `pytest -q`
- Build: `python -m PyInstaller ctxsnap_win.spec`
