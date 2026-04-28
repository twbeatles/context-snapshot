# CtxSnap Project Structure Analysis

- Updated: 2026-04-28
- Base branch: `main`
- Reviewed against: `README.md`, `README.en.md`, `CLAUDE.md`, `gpt.md`, `FEATURE_IMPLEMENTATION_REVIEW.md`, current implementation, tests, `.gitignore`, and `ctxsnap_win.spec`

## 1. High-level summary

CtxSnap is no longer a monolithic single-window script. The current codebase is split into:

- `services/` for business logic and migration helpers
- `core/` for cross-cutting infrastructure such as logging, workers, security, and sync
- `ui/main_window_sections/` for focused functional slices of the desktop UI
- `ui/dialogs/` for reusable modal workflows
- `tests/` for migration, sync, backup encryption, search, export helper, automation, dialog, and Git helper coverage

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
├── FEATURE_IMPLEMENTATION_REVIEW.md
├── tests/
│   ├── test_automation_helpers.py
│   ├── test_backup_encryption.py
│   ├── test_dialog_behaviors.py
│   ├── test_git_helpers.py
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
- `dialogs/history.py`: restore history, compare, and sync conflict inspection dialogs

### 3.3 Service/core split

- `SnapshotService`: schema migration, `rev/updated_at`, tombstone normalization/pruning, latest snapshot selection
- `SearchService`: free-text search plus field-query parsing and runtime snapshot-assisted matching
- `RestoreService`: restore defaults and restore-profile resolution
- `SecurityService`: DPAPI envelope encryption/decryption and sensitive-field stripping helpers
- `SyncEngine`: pull/merge/push, conflict recording with local/remote payload preservation, tombstone-aware deletion propagation

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
  - language-aware default tags for new/reset settings
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
- Existing DPAPI envelopes are preserved when raw encrypted snapshots are touched for metadata-only edits.
- This prevents note/TODO/process/app plaintext from being written back accidentally after decryption and prevents encrypted payload loss.

### 5.2 Search cache hardening

- `index.search_blob` no longer stores decrypted sensitive text.
- Free-text search still works by loading and matching decrypted content in memory when needed, even if a public non-sensitive cache blob already exists.
- Field queries (`todo:`, `note:`, `process:`, `app:`) continue to use runtime snapshot loading.
- Windows path queries preserve backslashes in the parser.

### 5.3 Restore and settings corrections

- `Restore Last` now chooses the newest item by `created_at`, then `updated_at`, then `id`.
- Restore History can rerun entries through double-click or Restore Again.
- Restore preview receives the checklist default explicitly instead of forcing it on.
- `default_root` is now Settings-owned state only; snapshot save/edit no longer rewrites it.
- Backup import asks whether to apply an imported `default_root` or keep the local one.
- `auto_backup_last` and `onboarding_shown` are preserved as local operational metadata during settings import.
- Auto backup failures no longer update `auto_backup_last`.
- Quick Snapshot seeds root/tags from the most recent snapshot, and TODO validation is disabled when TODO capture is disabled.

### 5.4 Sync deletion propagation

- Snapshot deletes now create top-level index tombstones.
- Sync merges snapshot maps and tombstone maps together.
- Tombstones are retained for 30 days and prevent stale remote snapshot resurrection.
- Same-revision conflicts preserve local and remote payloads in `sync_conflicts.json`; remote payloads are not overwritten by the local fallback winner.
- External backup/sync snapshot ids are validated before file writes.

### 5.5 Export UX

- Snapshot export and weekly report export now force an explicit choice between:
  - `Full export`
  - `Redacted export`
- Redacted export removes plaintext sensitive fields and the DPAPI envelope.
- Redacted export now also removes root/workspace/recent files/Git state and anonymizes title/tags.

### 5.6 Git and security operations

- Git discovery uses `git -C` rather than direct `.git` directory checks, supporting subdirectories and worktrees.
- Git auto-snapshot comparison includes branch, sha, dirty, changed, staged, and untracked state.
- Existing plaintext snapshots are encrypted only through the manual Settings security migration, which creates a safety backup first.
- New/reset settings use language-aware default tags without overwriting existing user tags.

## 6. Documentation and packaging alignment

- `README.md` and `README.en.md` now describe:
  - explicit `Default Root`
  - saved-query dropdown behavior
  - runtime-only sensitive search matching
  - tombstone-based sync deletes
  - `Full export` vs `Redacted export`
  - restore history rerun, sync conflict inspection, manual security migration, language-aware tags, and default-root import behavior
- `CLAUDE.md` and `gpt.md` now reflect the current schema and operational rules.
- `ctxsnap_win.spec` was reviewed for the new dialog/security/sync code. New UI lives inside existing hidden-import modules, so no spec change is required.
- `.gitignore` now also excludes installer/release artifacts such as `installer/Output/`, archive files, MSI, and PDB files.

## 7. Remaining improvement opportunities

- Cloud sync still uses a stub provider; real remote-provider support remains open.
- Sync conflict inspection now has a dedicated read-only UI; full conflict resolution/merge editing remains open.
- Export UX could later grow a richer preview/summary dialog.
- Search presets are quick-apply from the main window, but editing still lives in Settings only.
