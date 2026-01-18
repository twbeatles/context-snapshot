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
- **Search/Filter**: title/root/tag search + tag filter + pinned-only
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

### 0) Taskbar (running apps) snapshot/restore option
- **Include taskbar app list** in snapshots, and optionally relaunch them on restore.
- Example behavior
  - Save active app processes/windows at snapshot time
  - Restore by checking “Restore running apps”
- Implementation hints
  - Use Windows API to collect top-level windows/processes
  - Add a `running_apps` section in snapshot data
  - Relaunch by app path/args, with user-facing failure handling

### 1) Search/Filter improvements
- Expand search to notes/TODOs/recent files
- “Last N days” filter, “multi-tag” filter
- Sorting options (recent/pinned/title)

### 2) Performance & scaling
- Exclude folders for recent-file scans (`.git`, `node_modules`, `venv`, etc.)
- Time-bounded scanning and background collection
- Virtualized list for large snapshot counts

### 3) Restore experience
- Add “run only selected apps” checkbox in Restore Preview
- Auto-show a “session start checklist” after restore
- Restore history/success logs

### 4) Team collaboration
- Snapshot sharing (read-only link/file export)
- Team tags/templates
- Auto-generated weekly summary reports

### 5) Automation/Integrations
- Auto snapshot on schedule/events (e.g., end of work)
- Auto snapshot on Git commit/branch changes
- Send snapshot summaries to Slack/Notion

### 6) Privacy/Security
- Exclusion patterns for sensitive files/folders
- Snapshot encryption (local password/keychain)
- Toggles for stored data scope (processes/recent files)
