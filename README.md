# CtxSnap (Windows)

> English version: [README.en.md](README.en.md)

PySide6 기반 **작업 컨텍스트 스냅샷** 도구입니다. 현재 작업 맥락(폴더, 메모, TODO, 최근 파일, 실행 중 프로세스 등)을 한 번에 저장하고, 나중에 빠르게 복원할 수 있도록 돕습니다.

## 왜 필요한가요?
- “어디까지 했지?”가 반복되는 맥락 전환 비용을 줄입니다.
- TODO 3개를 강제하여 **다음 행동**을 분명히 남깁니다.
- 복원 시 폴더/터미널/VSCode를 한 번에 열어 흐름을 빠르게 되살립니다.

## 주요 기능
- **Global hotkey (설정 가능)**: 기본 **Ctrl + Alt + S** → Quick Snapshot
- **TODO 3개 필수** (다음 행동 3개)
- **Restore는 미리보기(Preview) 후 실행** (설정 가능)
- **Tray 상주**: Quick Snapshot / Restore Last / Open App Folder / Quit
- Snapshot을 **VSCode로 열기** (`code` 명령이 PATH에 있을 때)
- VSCode **.code-workspace** 파일 저장/복원 지원
- Git repo이면 제목 자동 추천(브랜치 + 최근 커밋 제목)
- **Tags / Pin**: 태그(업무/개인/부동산/정산 등)와 고정(Pin), 필터링
- **검색/필터**: 제목/루트/태그 + 메모/TODO/최근 파일/프로세스/앱까지 검색, 최근 N일/태그 복수 선택/정렬 옵션
- **최근 파일 스캔 제어**: 제외/포함 패턴, 스캔 제한, 백그라운드 수집 옵션
- **복원 체크리스트/히스토리**: 복원 완료 후 TODO 체크리스트, 히스토리 뷰어
- **자동 스냅샷**: 주기적 자동 저장 또는 Git 변경 감지 기반
- **대규모 스냅샷 대응**: 가상 리스트(virtualized list) + 페이지네이션/아카이빙으로 목록 렌더링 최적화
- **템플릿**: 자주 쓰는 TODO/태그/메모 템플릿 저장/적용
- **스냅샷 비교**: 두 스냅샷의 차이를 비교
- **자동 백업/아카이빙 정책**: 일정 간격 백업, 오래된 스냅샷 자동 아카이브
- **온보딩 가이드(앱 내)**: 첫 실행 시 간단한 사용법 안내 (Help→Onboarding, 트레이 메뉴에서 재오픈 가능)

## 스냅샷에 저장되는 것
스냅샷은 JSON으로 저장되며, 다음 정보를 포함합니다:
- **기본 메타**: 제목, 생성 시각, 루트 폴더
- **메모와 TODO 3개**
- **태그/핀**
- **최근 파일 목록** (루트 하위의 최근 변경 파일)
- **실행 중 프로세스 요약** (필터된 목록)

> 보안/프라이버시가 걱정된다면, 추후 “최근 파일/프로세스 저장 제외” 옵션을 추가하는 것을 고려해볼 수 있습니다.

## UI 구성 요약
- **메인 화면**
  - 왼쪽: 검색/태그/핀/아카이브 필터 + 스냅샷 리스트(페이지네이션)
  - 오른쪽: 상세 내용 (메모, TODO, 프로세스, 최근 파일)
- **Settings 탭**
  - General: 최근 파일 개수/스캔 패턴/프로세스 키워드/아카이브 정책/자동 백업
  - General: 스냅샷 페이지 크기 설정
  - Restore: 복원 동작(폴더/터미널/VSCode) + 미리보기 기본값
  - Hotkey: 단축키 설정
  - Tags: 태그 추가/삭제
  - Templates: 템플릿 추가/삭제
  - Backup: 백업/복원/초기화

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

빌드 결과:
- `dist\\CtxSnap\\CtxSnap.exe`

## Installer (Inno Setup) (선택)
1) 먼저 EXE 빌드:
```bash
pyinstaller --noconfirm --clean ctxsnap_win.spec
```
2) Inno Setup 설치 후, `installer\\ctxsnap.iss`를 Inno Setup Compiler로 열어 빌드

결과: `CtxSnap_Setup.exe` (Output 폴더는 Inno Setup 설정에 따릅니다)

## 사용 팁
- VSCode `code` 명령: VSCode에서 `Shell Command: Install 'code' command in PATH`를 실행하면 설정할 수 있습니다.
- 프로젝트가 큰 경우, 최근 파일 수집이 느릴 수 있습니다. 필요하다면 “최근 파일 개수”를 줄여보세요.

## 추가로 생각해볼 만한 기능 아이디어
아래는 실제 사용성 향상을 위한 후보들입니다. 필요에 맞게 우선순위를 골라 적용하면 좋습니다.

### 0) 성능/스케일링 개선 (구현됨)
- 스냅샷 수가 많을 때 페이지네이션/아카이빙

### 1) 팀/협업 기능 (미구현)
- 스냅샷 공유(읽기 전용 링크)
- 팀 태그/템플릿 제공

### 2) 자동화/연동 (미구현)
- Slack/Notion으로 스냅샷 요약 전송

### 3) 프라이버시/보안 (미구현)
- 스냅샷 암호화(로컬 암호/키 체인 활용)
