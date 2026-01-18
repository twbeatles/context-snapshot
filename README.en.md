# CtxSnap (Windows)

> 한국어 버전: [README.md](README.md)

CtxSnap is a PySide6-based **work context snapshot** tool. It captures the current working context (folders, notes, TODOs, recent files, running processes, and more) in one shot and helps you restore it quickly later.

## Why it helps
- Reduces context-switching cost when you ask, “Where did I leave off?”
- Enforces **exactly three TODOs** to clarify your **next actions**.
- Restores your flow by reopening folders/terminals/VSCode in one go.

## Key features
- **Global hotkey (configurable)**: default **Ctrl + Alt + S** → Quick Snapshot
- **Exactly 3 TODOs required** (next actions)
- **Restore runs after Preview** (configurable)
- **Tray resident**: Quick Snapshot / Restore Last / Open App Folder / Quit
- Open snapshots in **VSCode** (when the `code` command is in PATH)
- Save/restore VSCode **.code-workspace** files
- Auto-suggest titles for Git repos (branch + latest commit subject)
- **Tags / Pin**: tags (work/personal/real estate/settlement, etc.), pinning, and filtering
- **Search/Filter**: search notes/TODOs/recent files/apps + multi-tag/last N days/sort options
- **Recent file scan controls**: exclude folders, scan limits, background collection
- **Restore checklist/history**: post-restore TODO checklist + `restore_history.json` log
- **Auto snapshots**: scheduled interval or Git-change triggers
- **In-app onboarding guide**: quick usage tips on first launch (Help → Onboarding, re-openable from tray)

## What gets stored in a snapshot
Snapshots are saved as JSON and include:
- **Base metadata**: title, created time, root folder
- **Notes + 3 TODOs**
- **Tags/Pin**
- **Recent files list** (recently modified files under the root)
- **Running process summary** (filtered list)

> If you’re concerned about security/privacy, consider adding a future option to exclude “recent files/processes.”

## UI overview
- **Main view**
  - Left: search/tag/pin filters + snapshot list
  - Right: details (notes, TODOs, processes, recent files)
- **Settings tab**
  - General: recent files count
  - Restore: restore actions (folders/terminal/VSCode) + default preview behavior
  - Hotkey: hotkey setting
  - Tags: add/remove tags
  - Backup: backup/restore/reset

## Storage
- `%APPDATA%\\ctxsnap\\`
  - `snapshots\\<id>.json`
  - `index.json`, `settings.json`
  - `logs\\ctxsnap.log`

## Run (dev)
```bash
pip install -r requirements.txt
python ctxsnap_win.py
```

## Build EXE (PyInstaller)
```bash
pip install -r requirements.txt
python -m PyInstaller ctxsnap_win.spec
```

Build output:
- `dist\\CtxSnap\\CtxSnap.exe`

## Installer (Inno Setup) (optional)
1) Build the EXE first:
```bash
pyinstaller --noconfirm --clean ctxsnap_win.spec
```
2) Install Inno Setup, then open `installer\\ctxsnap.iss` with Inno Setup Compiler to build

Result: `CtxSnap_Setup.exe` (output folder depends on Inno Setup settings)

## Usage tips
- VSCode `code` command: run `Shell Command: Install 'code' command in PATH` inside VSCode.
- If your project is large, recent-file scanning may be slow. Reduce the “recent files count” if needed.

## Additional feature ideas
Below are candidates for improving real-world usability. You can prioritize based on your needs.

### 0) Performance & scaling (not yet implemented)
- Virtualized list for large snapshot counts

### 1) Team collaboration (not yet implemented)
- Snapshot sharing (read-only link)
- Team tags/templates

### 2) Automation/Integrations (not yet implemented)
- Send snapshot summaries to Slack/Notion

### 3) Privacy/Security (not yet implemented)
- Snapshot encryption (local password/keychain)
