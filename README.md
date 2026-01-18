# CtxSnap (Windows)

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
- **검색/필터**: 제목/루트/태그 기반 검색 + 태그 필터 + Pinned only
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
  - 왼쪽: 검색/태그/핀 필터 + 스냅샷 리스트
  - 오른쪽: 상세 내용 (메모, TODO, 프로세스, 최근 파일)
- **Settings 탭**
  - General: 최근 파일 개수 설정
  - Restore: 복원 동작(폴더/터미널/VSCode) + 미리보기 기본값
  - Hotkey: 단축키 설정
  - Tags: 태그 추가/삭제
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

### 0) 작업표시줄(현재 실행 앱) 스냅샷/복원 옵션
- **윈도우 작업표시줄에 떠 있는 앱 목록을 스냅샷에 포함**하고, 복원 시 다시 실행하는 옵션
- 예시 동작
  - 스냅샷 시점에 활성화된 앱 프로세스/윈도우 목록을 저장
  - 복원 시 “현재 실행 앱 복원” 체크박스를 통해 선택적으로 재실행
- 구현 힌트
  - Windows API로 현재 열려 있는 최상위 윈도우/프로세스 목록을 수집
  - 스냅샷 저장 데이터에 `running_apps` 섹션 추가
  - 복원 시 앱 경로/실행 인자 기반으로 재실행 (실패 시 사용자 안내)

### 1) 검색/필터 강화
- 메모/ TODO / 최근 파일까지 검색 범위를 확장
- “최근 N일” 필터, “태그 복수 선택” 필터
- 리스트 정렬 옵션(최근순/핀 우선/제목순)

### 2) 성능/스케일링 개선
- 최근 파일 스캔 시 제외 폴더 설정(`.git`, `node_modules`, `venv` 등)
- 스캔 시간 제한 및 백그라운드 수집
- 스냅샷 수가 많을 때 가상 리스트(virtualized list)

### 3) 복원 경험 개선
- Restore Preview에 “선택된 앱만 실행” 체크
- 복원 완료 후 “체크리스트(세션 시작 루틴)” 자동 표시
- 복원 히스토리/성공 여부 로그

### 4) 팀/협업 기능
- 스냅샷 공유(읽기 전용 링크/파일 내보내기)
- 팀 태그/템플릿 제공
- 회고용 요약 리포트 자동 생성(주간 스냅샷 모음)

### 5) 자동화/연동
- 특정 시간/이벤트에 자동 스냅샷(작업 종료 시 등)
- Git 커밋/브랜치 변경 감지 후 자동 스냅샷
- Slack/Notion으로 스냅샷 요약 전송

### 6) 프라이버시/보안
- 민감 폴더/파일 제외 패턴
- 스냅샷 암호화(로컬 암호/키 체인 활용)
- 저장되는 데이터 범위 토글(프로세스/최근 파일)
