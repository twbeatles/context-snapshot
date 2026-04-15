# CtxSnap Project Structure Analysis

- Updated: 2026-04-15
- Base branch: `main`
- Reviewed against: `README.md`, `README.en.md`, `CLAUDE.md`, `gpt.md`, current implementation, tests, and `ctxsnap_win.spec`

## 1. High-level summary

CtxSnap is no longer a monolithic single-window script. The current codebase is split into:

- `services/` for business logic and migration helpers
- `core/` for cross-cutting infrastructure such as logging, workers, security, and sync
- `ui/main_window_sections/` for focused functional slices of the desktop UI
- `ui/dialogs/` for reusable modal workflows
- `tests/` for migration, sync, backup encryption, search, and export helper coverage

The project is in a healthy modularized state, and the recent review-driven changes tightened security and sync semantics without undoing that separation.

## 2. Current repository layout

```text
context-snapshot/
├── ctxsnap_win.py
├── ctxsnap_win.spec
├── requirements.txt
├── requirements-dev.txt
├── pyrightconfig.json
├── README.md
├── README.en.md
├── CLAUDE.md
├── gpt.md
├── PROJECT_STRUCTURE_ANALYSIS.md
├── tests/
│   ├── test_backup_encryption.py
│   ├── test_migration.py
│   ├── test_restore_actions_helpers.py
│   ├── test_search_service.py
│   ├── test_security_service.py
│   └── test_sync_engine.py
└── ctxsnap/
    ├── app_storage.py
    ├── constants.py
    ├── i18n.py
    ├── restore.py
    ├── utils.py
    ├── core/
    │   ├── logging.py
    │   ├── security.py
    │   ├── worker.py
    │   └── sync/
    │       ├── base.py
    │       ├── engine.py
    │       └── providers/
    │           ├── cloud_stub.py
    │           └── local.py
    ├── services/
    │   ├── backup_service.py
    │   ├── restore_service.py
    │   ├── search_service.py
    │   └── snapshot_service.py
    └── ui/
        ├── dialogs/
        ├── hotkey.py
        ├── main_window.py
        ├── main_window_sections/
        │   ├── automation.py
        │   ├── list_view.py
        │   ├── restore_actions.py
        │   ├── settings_backup.py
        │   └── snapshot_crud.py
        ├── models.py
        └── styles.py
```

## 3. Responsibility map

### 3.1 Startup and storage

- `ctxsnap_win.py` initializes the Qt application shell.
- `ensure_storage()` creates `%APPDATA%\ctxsnap\` storage and bootstrap files.
- `migrate_settings()` and `SnapshotService.migrate_index()` normalize old data at startup.

### 3.2 UI split

- `main_window.py`: top-level composition, shared widgets, menu wiring, saved-query dropdown orchestration
- `main_window_sections/snapshot_crud.py`: create/edit/delete/toggle metadata/detail rendering
- `main_window_sections/list_view.py`: search/filter/pagination/list population
- `main_window_sections/automation.py`: timers, archive policy, recent-file background updates, auto snapshots, sync scheduling
- `main_window_sections/settings_backup.py`: settings apply/import/export flows and safety rollback
- `main_window_sections/restore_actions.py`: restore flows, restore history, compare, export actions

### 3.3 Service/core split

- `SnapshotService`: schema migration, `rev/updated_at`, tombstone normalization/pruning, latest snapshot selection
- `SearchService`: free-text search plus field-query parsing and runtime snapshot-assisted matching
- `RestoreService`: restore defaults and restore-profile resolution
- `SecurityService`: DPAPI envelope encryption/decryption and sensitive-field stripping helpers
- `SyncEngine`: pull/merge/push, conflict recording, tombstone-aware deletion propagation

## 4. Data model notes

Storage root: `%APPDATA%\ctxsnap\`

- `settings.json`
  - `schema_version = 2`
  - `default_root`
  - `dev_flags`
  - `sync`
  - `security`
  - `search.saved_queries`
  - `restore_profiles`
- `index.json`
  - `schema_version`
  - `rev`
  - `updated_at`
  - `search_meta`
  - `snapshots`
  - `tombstones`
- `snapshots/<id>.json`
  - `schema_version`
  - `rev`
  - `updated_at`
  - `git_state`
  - optional DPAPI `sensitive` envelope

## 5. Recent review-driven implementation changes

### 5.1 Secure persistence paths

- Snapshot loading is now effectively split into:
  - raw persisted snapshot
  - decrypted UI/search view snapshot
- Background recent-file updates and metadata-only edits persist through the shared secure save path.
- This prevents note/TODO/process/app plaintext from being written back accidentally after decryption.

### 5.2 Search cache hardening

- `index.search_blob` no longer stores decrypted sensitive text.
- Free-text search still works by loading and matching decrypted content in memory when needed.
- Field queries (`todo:`, `note:`, `process:`, `app:`) continue to use runtime snapshot loading.

### 5.3 Restore and settings corrections

- `Restore Last` now chooses the newest item by `created_at`, then `updated_at`, then `id`.
- Restore preview receives the checklist default explicitly instead of forcing it on.
- `default_root` is now Settings-owned state only; snapshot save/edit no longer rewrites it.
- `auto_backup_last` and `onboarding_shown` are preserved as local operational metadata during settings import.

### 5.4 Sync deletion propagation

- Snapshot deletes now create top-level index tombstones.
- Sync merges snapshot maps and tombstone maps together.
- Tombstones are retained for 30 days and prevent stale remote snapshot resurrection.

### 5.5 Export UX

- Snapshot export and weekly report export now force an explicit choice between:
  - `Full export`
  - `Redacted export`
- Redacted export removes plaintext sensitive fields and the DPAPI envelope.

## 6. Documentation and packaging alignment

- `README.md` and `README.en.md` now describe:
  - explicit `Default Root`
  - saved-query dropdown behavior
  - runtime-only sensitive search matching
  - tombstone-based sync deletes
  - `Full export` vs `Redacted export`
- `CLAUDE.md` and `gpt.md` now reflect the current schema and operational rules.
- `ctxsnap_win.spec` was re-validated with `python -m PyInstaller ctxsnap_win.spec`; no spec change was required for the new functionality.

## 7. Remaining improvement opportunities

- Cloud sync still uses a stub provider; real remote-provider support remains open.
- Sync conflict inspection/resolution is recorded but still light on dedicated UI.
- Export UX could later grow a richer preview/summary dialog.
- Search presets are quick-apply from the main window, but editing still lives in Settings only.
