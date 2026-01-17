# CtxSnap (Windows)

PySide6 기반 **작업 컨텍스트 스냅샷** 도구입니다. 

## Features
- Global hotkey (설정 가능): 기본 **Ctrl + Alt + S** → Quick Snapshot
- TODO **3개 필수** (다음 행동 3개)
- Restore는 **미리보기(Preview) 후 실행** (설정 가능)
- **Tray 상주**: Quick Snapshot / Restore Last / Open App Folder / Quit
- Snapshot을 **VSCode로 열기** (`code` 명령이 PATH에 있을 때)
- VSCode **.code-workspace** 파일 저장/복원 지원
- Git repo이면 제목 자동 추천(브랜치 + 최근 커밋 제목)
- **Tags / Pin**: 태그(업무/개인/부동산/정산 등)와 고정(Pin), 필터링
- Settings 화면:
  - 단축키 변경(Ctrl/Alt/Shift/Key)
  - Restore 옵션(폴더/터미널/VSCode)
  - 최근 파일 개수 설정
  - Preview 기본값 토글
  - **설정 내보내기/가져오기** (PC 교체/재설치 대비)
  - 태그 추가/삭제

- **온보딩 가이드(앱 내)**: 첫 실행 시 간단한 사용법 안내가 뜨며, 메뉴(Help→Onboarding) 또는 트레이 메뉴에서 다시 열 수 있습니다.

## Storage
- `%APPDATA%\\ctxsnap\\`
  - `snapshots\\<id>.json`
  - `index.json`, `settings.json`

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

빌드 결과:
- `dist\\CtxSnap\\CtxSnap.exe`

## Installer (Inno Setup) (선택)
1) 먼저 EXE 빌드:
```bash
pyinstaller --noconfirm --clean ctxsnap_win.spec
```
2) Inno Setup 설치 후, `installer\\ctxsnap.iss`를 Inno Setup Compiler로 열어 빌드

결과: `CtxSnap_Setup.exe` (Output 폴더는 Inno Setup 설정에 따릅니다)

## Tips
- VSCode `code` 명령: VSCode에서 `Shell Command: Install 'code' command in PATH`를 실행하면 설정할 수 있습니다.
