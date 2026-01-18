## CtxSnap GPT Notes

### Project summary
- CtxSnap is a PySide6 Windows app that captures and restores working context snapshots (root folder, note, TODOs, recent files, filtered processes, and running apps). 
- Snapshots and settings are stored under `%APPDATA%\ctxsnap\` as JSON.

### Key files
- `ctxsnap_win.py`: main application logic and UI.
- `README.md`: user-facing documentation.

### Usage
- Run dev build: `pip install -r requirements.txt` then `python ctxsnap_win.py`.
- Build EXE: `python -m PyInstaller ctxsnap_win.spec`.

### Notes for contributors
- Be mindful of performance for filesystem scans; prefer caps and exclusions.
- Avoid storing sensitive data by default; capture toggles exist in Settings.
