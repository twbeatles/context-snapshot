## CtxSnap GPT Notes

### Project summary
- Windows-only PySide6 app for capturing and restoring working-context snapshots.
- Current architecture is service-oriented with `MainWindow` split into focused section mixins.
- Storage lives under `%APPDATA%\ctxsnap\` with schema migration, atomic JSON writes, backup import/export, DPAPI security, and local sync support.

### Key modules
- `ctxsnap/app_storage.py`: storage paths, migrations, atomic JSON IO, backup import/export.
- `ctxsnap/services/snapshot_service.py`: index/snapshot migration, revision metadata, tombstone helpers, latest-item selection.
- `ctxsnap/services/search_service.py`: free-text and field-query parsing/matching.
- `ctxsnap/core/security.py`: DPAPI envelope encryption/decryption for sensitive snapshot fields.
- `ctxsnap/core/sync/*`: sync provider protocol, merge engine, local/cloud-stub providers.
- `ctxsnap/ui/main_window.py`: orchestration shell and top-level UI composition.
- `ctxsnap/ui/main_window_sections/*`: functional slices for automation, list view, CRUD, settings/backup, restore actions.

### Data files
- `%APPDATA%\ctxsnap\snapshots\<id>.json`
- `%APPDATA%\ctxsnap\index.json`
- `%APPDATA%\ctxsnap\settings.json`
- `%APPDATA%\ctxsnap\restore_history.json`
- `%APPDATA%\ctxsnap\sync_conflicts.json`
- `%APPDATA%\ctxsnap\sync_state.json`
- `%APPDATA%\ctxsnap\logs\ctxsnap.log`

### Important schema bits
- `settings.schema_version = 2`
- `settings.default_root`: explicit automation root, changed only from Settings.
- `settings.search.saved_queries`: search presets managed in Settings and applied from the main-window dropdown.
- `snapshot.schema_version = 2`
- Snapshot revision metadata: `rev`, `updated_at`
- `index.tombstones = [{"id": "...", "deleted_at": "..."}]` with 30-day retention
- DPAPI envelope shape: `{"enc":"dpapi","v":1,"blob":"<base64>"}`

### Feature flags (`settings.dev_flags`)
- `sync_enabled`
- `security_enabled`
- `advanced_search_enabled`
- `restore_profiles_enabled`

### Current behavior notes
- Sync merge still prefers latest `(rev, updated_at)`; same-key payload conflicts are recorded in the conflict queue.
- Snapshot deletion now propagates through sync via 30-day tombstones to prevent stale resurrection.
- Sensitive fields are persisted through raw/encrypted snapshot paths. Background recent-file updates and archive metadata updates do not rewrite decrypted plaintext back to disk.
- Decrypted sensitive text is never persisted into `index.json` `search_blob`. Free-text search may decrypt at runtime only.
- Decryption failures surface `_security_error` to the detail panel and restore preview instead of failing silently.
- `Export Selected Snapshot` and `Export Weekly Report` require `Full export` vs `Redacted export` when sensitive data is present or decryption has failed.
- `Restore Last` uses newest `created_at`, then `updated_at`, then `id` as a tie-breaker.
- Close (X) minimizes to tray; full exit comes from tray `Quit`.

### Build / test
- Run app: `python ctxsnap_win.py`
- Type check: `python -m pyright`
- Test: `python -m pytest -q`
- Build: `python -m PyInstaller ctxsnap_win.spec`
- Packaging check: `ctxsnap_win.spec` was validated successfully with PyInstaller after the security/sync/export updates.

### Repo guardrails
- `pyrightconfig.json`: shared Windows typing config, Python 3.11 target.
- `.editorconfig`: UTF-8 + CRLF + final-newline/trailing-space policy.
- `.gitattributes`: repository text EOL normalization.
- CI (`.github/workflows/ci.yml`): runs `pyright` then `pytest`.
