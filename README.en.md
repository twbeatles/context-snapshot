# CtxSnap (Windows)

> 한국어 버전: [README.md](README.md)

**CtxSnap** is a PySide6-based **working context snapshot** tool. It saves your current work context (folders, notes, TODOs, recent files, running processes, etc.) all at once and helps you quickly restore it later.

---

## 📋 Table of Contents

1. [Why Do You Need This?](#why-do-you-need-this)
2. [Key Features](#key-features)
3. [Installation](#installation)
4. [How to Use](#how-to-use)
5. [Feature Guide](#feature-guide)
6. [Settings](#settings)
7. [Data Storage Location](#data-storage-location)
8. [Developer Guide](#developer-guide)
9. [Troubleshooting](#troubleshooting)
10. [Roadmap](#roadmap)

---

## Why Do You Need This?

- 🔄 **Reduce context switching costs** - No more "Where was I?"
- ✅ **Mandatory 3 TODOs** - Clearly define your **next actions**
- 🚀 **One-click restore** - Open folder/terminal/VSCode all at once

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Global Hotkey** | Quick snapshot with `Ctrl + Alt + S` from anywhere |
| **Mandatory 3 TODOs** | Always record 3 things to do next |
| **Restore Preview** | Review content before restoring |
| **System Tray** | Background operation, quick access menu |
| **VSCode Integration** | Open VSCode project from snapshot |
| **Git Integration** | Auto-suggest title from branch + commit info |
| **Tags/Pin** | Categorize (work/personal) and pin important snapshots |
| **Unified Search** | Search across title/notes/TODO/files/processes |
| **Field Query Search** | Advanced query tokens like `tag:`, `root:`, `todo:` (dev flag) |
| **Auto Snapshot** | Auto-save periodically or on Git changes |
| **Templates** | Save frequently used configurations |
| **Snapshot Comparison** | Compare differences between two snapshots |
| **Backup/Restore** | Backup settings and snapshot data |
| **Selective DPAPI Encryption** | Encrypt note/TODO/process/app fields selectively (dev flag) |
| **Local Sync Engine** | Plugin-based sync with local provider and conflict queue |
| **Restore Profiles** | Save/apply restore option presets (dev flag) |
| **Restore History** | Review and re-run recent restore actions |
| **Onboarding** | Built-in first-run usage guide |
| **Bilingual UI** | Korean/English support (auto-detect + manual switch) |

---

## Installation

### Option 1: Installer (Recommended)

1. Download `CtxSnap_Setup.exe` from [Releases](https://github.com/twbeatles/context-snapshot/releases)
2. Run the installer
3. Launch **CtxSnap** from the Start menu

### Option 2: Portable

1. Download `CtxSnap.zip` from [Releases](https://github.com/twbeatles/context-snapshot/releases)
2. Extract and run `CtxSnap.exe`

### Option 3: From Source

```bash
# Clone repository
git clone https://github.com/twbeatles/context-snapshot.git
cd context-snapshot

# Install dependencies
pip install -r requirements.txt

# Run
python ctxsnap_win.py
```

---

## How to Use

### 🚀 Quick Start

#### 1. Create Your First Snapshot

1. Launch **CtxSnap**
2. Click **+ New Snapshot** button (or press `Ctrl + Alt + S`)
3. Fill in the work information:
   - **Title**: A title representing your current work status
   - **Root Folder**: Select the project folder you're working on
   - **Note**: A brief note about the current state
   - **3 TODOs**: Three things to do next (required!)
   - **Tags**: Select categorization tags
4. Click **Save**

#### 2. Restore a Snapshot

1. Select a snapshot from the list
2. Click **Restore** button
3. Confirm restore options (in preview mode):
   - ✅ Open folder
   - ✅ Open terminal
   - ✅ Open VSCode
   - ⬜ Restore running apps (disabled by default)
4. Click **Execute Restore**

#### 3. Using the Global Hotkey

- Press `Ctrl + Alt + S` **from any app** to show quick snapshot dialog
- Uses root folder and tags from the previous snapshot as defaults

---

### 📊 UI Layout

```
┌────────────────────────────────────────────────────────────┐
│ CtxSnap                                        [─] [□] [×] │
├────────────────────────────────────────────────────────────┤
│  🔍 Search...                   [Tags ▼] [Sort ▼] [+ New]  │
├─────────────────────────┬──────────────────────────────────┤
│                         │                                  │
│  📁 feature/auth work   │  📋 Details                       │
│     2024-01-15 14:30    │                                  │
│     work, dev           │  Title: feature/auth work         │
│                         │  Root: C:\Projects\my-app         │
│  📁 API integration     │                                  │
│     2024-01-14 16:22    │  📝 Note                          │
│     work                │  Working on login feature...      │
│                         │                                  │
│  📁 Document cleanup    │  ✅ TODO                          │
│     2024-01-13 09:15    │  1. Complete API integration      │
│     personal            │  2. Write test cases              │
│                         │  3. Submit PR                     │
│  [< Prev] [1/5] [Next >]│                                  │
│                         │  📂 Recent Files (5)              │
│                         │  • src/auth.py                   │
│                         │  • tests/test_auth.py            │
│                         │                                  │
│                         │  ⚙️ Processes (3)                 │
│                         │  • code.exe                      │
│                         │  • chrome.exe                    │
│                         │                                  │
│                         │  [Restore] [Edit] [Delete] [Compare] │
└─────────────────────────┴──────────────────────────────────┘
```

---

## Feature Guide

### 🏷️ Tag Management

Use tags to categorize your snapshots.

**Default Tags:**
- Work
- Personal
- Real Estate
- Settlement

**Adding Custom Tags:**
1. Settings → Tags tab
2. Enter new tag name
3. Click **Add**

**Filter by Tags:**
- Select one or more tags from the dropdown at the top
- Only snapshots with selected tags will be shown

---

### 📌 Pin Feature

Pin important snapshots to the top.

1. Select a snapshot
2. Right-click → **Pin** or click the pin icon in the detail panel
3. Pinned snapshots appear at the top with a 📌 icon

---

### 🔍 Search Feature

The search bar provides unified search across:

- **Title**: Snapshot title
- **Root folder**: Project path
- **Tags**: Tag names
- **Note**: Note content
- **TODO**: TODO items
- **Recent files**: Saved file paths
- **Processes**: Running process names

**Search Tips:**
- Space-separated keywords (AND condition)
- Case-insensitive
- With advanced search enabled, field queries are supported: `tag:work root:context-snapshot todo:deploy`

---

### 📋 Templates

Save frequently used configurations as templates.

**Create a Template:**
1. Settings → Templates tab
2. Click **New Template**
3. Set template name, default TODOs, tags, and note
4. Click **Save**

**Apply a Template:**
1. In the new snapshot dialog
2. Select from **Apply Template** dropdown
3. Choose the desired template → values auto-fill

---

### ⚡ Auto Snapshot

Automatically create snapshots without manual saving.

**Periodic Auto Snapshot:**
1. Settings → General tab
2. Set **Auto snapshot interval (minutes)** (0 = disabled)
3. Example: Enter `30` for auto-save every 30 minutes (headless, no dialog)

**Git Change Detection:**
1. Settings → General tab
2. Check **Auto snapshot on Git change**
3. Auto-saves when Git status (branch, commit, etc.) changes (headless, no dialog)

**Auto-save deduplication:**
- If the core context (root/workspace/note/TODO/tags/Git state) has not changed, auto snapshot is skipped.

---

### 🔄 Snapshot Comparison

Compare differences between two snapshots.

1. Select the first snapshot
2. Hold `Ctrl` and select the second snapshot
3. Click **Compare** button
4. View comparison results:
   - Added items (green)
   - Removed items (red)
   - Changed items (yellow)

---

### 📜 Restore History

Review previously executed restore actions and inspect outcomes.

1. Menu → Tools → **Open Restore History**
2. Select an entry to see details (timestamp, options, failures)
3. Use it as a quick audit trail for restore troubleshooting

---

### 👋 Onboarding

CtxSnap includes a built-in onboarding guide.

1. It appears automatically on first launch
2. You can reopen it from tray menu → **Onboarding**
3. Covers snapshot creation, restore flow, tags, and settings

---

### 🌐 Language Support

CtxSnap supports Korean and English.

1. **Auto detect** from system locale on startup
2. **Manual override** in Settings → General (restart required)

---

### 💾 Backup and Restore

Backup your settings and snapshot data.

**Create Backup:**
1. Settings → Backup tab
2. Click **Export Backup**
3. Choose save location
4. Select options:
   - ✅ Include settings
   - ✅ Include snapshot data

**Restore from Backup:**
1. Settings → Backup tab
2. Click **Import Backup**
3. Select backup file
4. Choose `Apply now` for immediate apply, or `Keep in dialog` to apply on Save.

---

### 🖥️ System Tray

CtxSnap resides in the system tray.

**Tray Menu:**
- **Quick Snapshot**: Create a quick snapshot
- **Restore Last**: Restore the most recent snapshot
- **Open App Folder**: Open data folder
- **Settings**: Open settings
- **Quit**: Exit the app

**Minimize to Tray:**
- Clicking the close button (×) minimizes to tray
- To fully exit: Tray menu → Quit

---

## Settings

### General Tab

| Setting | Description | Default |
|---------|-------------|---------|
| Default Root Folder | Default folder for new snapshots | `%USERPROFILE%` |
| Recent Files Count | Number of recent files to save | `30` |
| Exclude Directories | Folders to exclude from scan | `.git, node_modules, __pycache__` |
| Process Keywords | Filter for processes to save | `code, chrome, notion, slack` |
| Auto Snapshot Interval | Minutes, 0=disabled | `0` |
| Git Change Detection | Auto-save on Git changes | `false` |

### Developer/Sync/Security/Search (inside General tab)

| Setting | Description | Default |
|---------|-------------|---------|
| Enable Sync Feature | Enable sync feature set | `false` |
| Enable Security Feature | Enable DPAPI security flow | `false` |
| Enable Advanced Search | Enable field query parser | `false` |
| Enable Restore Profiles | Enable restore profile presets | `false` |
| Sync Provider | Sync provider (`local`/`cloud_stub`) | `local` |
| Local Sync Root | Local sync target folder | `%APPDATA%\\ctxsnap\\sync_local` |
| Sync Interval | Auto sync interval in minutes, 0=off | `0` |
| Enable DPAPI | Turn on Windows DPAPI | `false` |
| Encrypt Note/TODO/Processes/Running Apps | Selective sensitive-field encryption | `true` |
| Enable Field Query | Enable `tag:`, `root:`, `todo:` tokens | `true` |
| Saved Queries | Search presets | `[]` |

### Restore Tab

| Setting | Description | Default |
|---------|-------------|---------|
| Open Folder | Open root folder on restore | `true` |
| Open Terminal | Open terminal on restore | `true` |
| Open VSCode | Open VSCode on restore | `true` |
| Restore Apps | Restore running apps | `false` |
| Preview | Show preview before restore | `true` |

### Hotkey Tab

| Setting | Description | Default |
|---------|-------------|---------|
| Enable Hotkey | Enable global hotkey | `true` |
| Modifier Keys | Ctrl, Alt, Shift combination | `Ctrl + Alt` |
| Main Key | Trigger key | `S` |

---

## Data Storage Location

All data is stored in `%APPDATA%\ctxsnap\`.

```
%APPDATA%\ctxsnap\
├── snapshots/              # Individual snapshot JSON files
│   ├── 20240115-143022.json
│   ├── 20240114-162235.json
│   └── ...
├── index.json              # Snapshot index (search cache)
├── settings.json           # App settings
├── restore_history.json    # Restore history
├── sync_conflicts.json     # Sync conflict queue
├── sync_state.json         # Sync state (cursor/last sync)
└── logs/
    └── ctxsnap.log         # Log file (rotating)
```

**Open Folder:** Tray menu → Open App Folder

---

## Developer Guide

### Development Environment Setup

```bash
# Clone repository
git clone https://github.com/twbeatles/context-snapshot.git
cd context-snapshot

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run in development mode
python ctxsnap_win.py
```

### Tests

```bash
pytest -q
```

### Static Type Check (Pylance/pyright)

```bash
pyright
```

- Uses the repository-root `pyrightconfig.json`.
- CI runs both `pyright` and `pytest`.

### Build EXE (PyInstaller)

```bash
# Install PyInstaller
pip install pyinstaller

# Run build
python -m PyInstaller ctxsnap_win.spec

# Result: dist\CtxSnap\CtxSnap.exe
```

### Build Installer (Inno Setup)

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Build EXE first (`python -m PyInstaller ctxsnap_win.spec`)
3. Open `installer/ctxsnap.iss` in Inno Setup Compiler
4. Compile → Creates `CtxSnap_Setup.exe`

### Project Structure

| File/Folder | Description |
|-------------|-------------|
| `ctxsnap_win.py` | Main application (UI + logic) |
| `ctxsnap/` | Core package |
| `ctxsnap/core/` | Logging/worker/security/sync engine |
| `ctxsnap/core/sync/` | Sync protocol + engine + providers |
| `ctxsnap/services/` | Snapshot/Restore/Backup/Search services |
| `ctxsnap/ui/main_window_sections/` | Split sections for MainWindow behaviors |
| `ctxsnap/app_storage.py` | Storage, migrations, backup I/O |
| `ctxsnap/utils.py` | Utility functions |
| `assets/` | Icons/images |
| `tests/` | pytest-based automated tests |
| `.github/workflows/ci.yml` | Windows CI pipeline (`pyright`, `pytest`) |
| `pyrightconfig.json` | Shared Pylance/pyright type-check config |
| `.editorconfig` | UTF-8 + CRLF + formatting guardrails |
| `.gitattributes` | Text EOL normalization policy |
| `installer/` | Inno Setup scripts |

---

## Troubleshooting

### ❓ VSCode won't open

**Cause:** `code` command not in PATH

**Solution:**
1. Open VSCode
2. `Ctrl + Shift + P` → Run "Shell Command: Install 'code' command in PATH"
3. Restart terminal

---

### ❓ File scanning is too slow

**Cause:** Large project folder

**Solution:**
1. Settings → General tab
2. Reduce **Recent Files Count** (e.g., 30 → 15)
3. Add `node_modules`, `dist`, `build`, etc. to **Exclude Directories**

---

### ❓ Hotkey doesn't work

**Cause:** Another app using the same hotkey or hotkey disabled

**Solution:**
1. Settings → Hotkey tab
2. Verify **Enable Hotkey** is checked
3. Change to a different combination (e.g., `Ctrl + Alt + Q`)

---

### ❓ I want to completely delete snapshot data

**Solution:**
1. Settings → Backup tab
2. **Restore Defaults** resets settings only.
3. To remove everything including snapshots, delete `%APPDATA%\ctxsnap` manually.

---

### ❓ Where are the log files?

**Location:** `%APPDATA%\ctxsnap\logs\ctxsnap.log`

Please attach this file when creating issues.

---

## Roadmap

### 🔜 Planned Features

- [ ] Cross-platform support (macOS, Linux)
- [ ] Team collaboration (snapshot sharing)
- [x] Local sync provider + conflict queue
- [x] DPAPI-based selective encryption (feature-flagged)
- [ ] Production cloud provider integration
- [ ] Slack/Notion integration
- [ ] Search UX improvements for saved queries

### 💡 Feature Suggestions

Have a new feature idea? Please suggest it in [Issues](https://github.com/twbeatles/context-snapshot/issues)!

---

## License

MIT License

---

## Contributing

1. Fork
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Create Pull Request

---

**Made with ❤️ for productivity lovers**
