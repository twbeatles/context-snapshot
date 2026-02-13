# GEMINI.md - CtxSnap 프로젝트 가이드

> Gemini AI가 이 프로젝트를 이해하고 작업할 때 참고하는 문서입니다.

## 프로젝트 요약

| 항목 | 내용 |
|------|------|
| **이름** | CtxSnap (Context Snapshot) |
| **언어** | Python 3.x |
| **UI 프레임워크** | PySide6 |
| **플랫폼** | Windows 전용 |
| **용도** | 작업 컨텍스트 스냅샷 저장/복원 도구 |

---

## 핵심 목적

1. 현재 작업 상태를 스냅샷으로 저장 (폴더, 메모, TODO, 실행 앱)
2. 나중에 동일한 작업 환경으로 빠르게 복원
3. TODO 3개 필수 입력으로 다음 작업 명확화

---

## 파일 구조

### 진입점 및 핵심 파일
```
ctxsnap_win.py              # 메인 애플리케이션 진입점
ctxsnap/
├── core/                   # 핵심 로직 (로깅, 워커)
├── ui/                     # UI 컴포넌트 (Window, Dialogs)
├── i18n.py                 # 다국어 처리
├── app_storage.py          # 고급 스토리지 로직
├── utils.py                # 유틸리티
└── restore.py              # 복원 헬퍼
```

### 설정 및 데이터
```
%APPDATA%\ctxsnap\
├── snapshots/<id>.json     # 개별 스냅샷
├── index.json              # 스냅샷 인덱스
├── settings.json           # 앱 설정
└── logs/ctxsnap.log        # 로그
```

### 빌드/배포
```
ctxsnap_win.spec            # PyInstaller 스펙
requirements.txt            # Python 의존성
installer/                  # Inno Setup 스크립트
```

---

## 핵심 클래스 및 함수

### UI 클래스 (ctxsnap/ui/)

| 클래스 | 위치 | 역할 |
|--------|------|------|
| `MainWindow` | `main_window.py` | 메인 윈도우 |
| `SnapshotDialog` | `dialogs/snapshot.py` | 스냅샷 생성/편집 |
| `SettingsDialog` | `dialogs/settings.py` | 설정 다이얼로그 |
| `OnboardingDialog` | `dialogs/onboarding.py` | 첫 실행 가이드 |
| `RestoreHistoryDialog` | `dialogs/history.py` | 복원 기록 |
| `HotkeyFilter` | `hotkey.py` | 글로벌 핫키 필터 |

### 유틸리티 함수 (ctxsnap/utils.py)

| 함수 | 역할 |
|------|------|
| `recent_files_under(root, limit)` | 루트 아래 최근 파일 스캔 |
| `list_processes_filtered(keywords)` | 프로세스 필터링 |
| `list_running_apps()` | 실행 중 앱 목록 |
| `restore_running_apps(apps)` | 앱 복원 실행 |
| `build_search_blob(snap)` | 검색 인덱스 문자열 |

### 스토리지 함수

| 함수 | 위치 | 역할 |
|------|------|------|
| `load_json()` | app_storage.py | JSON 읽기 (예외 처리 + 기본값 반환) |
| `save_json()` | app_storage.py | JSON 쓰기 (원자적 쓰기 - temp+rename) |
| `ensure_storage()` | app_storage.py | 초기화 |
| `migrate_settings()` | app_storage.py | 설정 마이그레이션 |
| `export_backup_to_file()` | app_storage.py | 백업 내보내기 |
| `open_folder()` | restore.py | 폴더 열기 (Tuple 반환) |
| `open_terminal_at()` | restore.py | 터미널 열기 (Tuple 반환) |
| `open_vscode_at()` | restore.py | VSCode 열기 (Tuple 반환) |

---

## 주요 기능 플로우

### 스냅샷 생성
```
SnapshotDialog._create()
  → collect_recent_files (background)
  → collect_processes
  → collect_running_apps
  → save_snapshot → write to <id>.json
  → update index.json
```

### 스냅샷 복원
```
MainWindow._restore_by_id()
  → read_snapshot
  → open_folder (os.startfile)
  → open_terminal (subprocess)
  → open_vscode (code command)
  → restore_running_apps
  → append_restore_history
```

### 글로벌 핫키
```
register_hotkey() → Windows RegisterHotKey API
HotkeyFilter.nativeEventFilter()
  → emit hotkeyPressed signal
  → MainWindow._quick_snapshot()
```

---

## 개발 명령어

```bash
# 개발 실행
pip install -r requirements.txt
python ctxsnap_win.py

# EXE 빌드
python -m PyInstaller ctxsnap_win.spec
# 결과: dist/CtxSnap/CtxSnap.exe
```

---

## 코딩 컨벤션

### 필수 규칙
- **타입 힌트 사용**: `def func(x: str) -> bool:`
- **예외 처리**: 파일/프로세스 작업은 반드시 try-except
- **원자적 쓰기**: `save_json()`은 temp+rename 패턴 사용
- **성능 제한**: 파일 스캔은 `scan_limit`, `scan_seconds` 적용
- **백그라운드 처리**: Heavy 작업은 QRunnable 사용
- **리소스 정리**: `closeEvent`에서 워커 스레드 정리

### 스타일 가이드
```python
from __future__ import annotations  # 상단 필수
from dataclasses import dataclass   # 데이터 클래스 활용
from typing import List, Dict, Optional  # 타입 힌트
```

### 새 설정 키 추가 시
1. `app_storage.py`의 `migrate_settings()`에 기본값 추가
2. `app_storage.py`의 `ensure_storage()` 로직 확인

### 상수 관리
- `APP_NAME` 등 상수는 `ctxsnap/constants.py`에서만 정의
- 다른 파일에서는 `from ctxsnap.constants import APP_NAME` 사용

### i18n 규칙
- 모든 사용자 메시지는 `tr()` 함수 사용
- 신규 키는 `i18n.py`의 en/ko 섹션 모두에 추가

### 안전한 파일 처리
- `save_json()`: `os.replace()` 사용 (원자적)
- subprocess: 타임아웃 필수 (예: `timeout=5`)

---

## 설정 구조 (settings.json)

```json
{
  "default_root": "C:\\Users\\...",
  "hotkey_enabled": true,
  "hotkey": { "ctrl": true, "alt": true, "shift": false, "vk": "S" },
  "recent_files_limit": 30,
  "recent_files_exclude_dirs": [".git", "node_modules", "__pycache__"],
  "process_keywords": ["code", "chrome", "notion", "slack"],
  "auto_snapshot_minutes": 0,
  "auto_snapshot_on_git_change": false,
  "restore": {
    "open_folder": true,
    "open_terminal": true,
    "open_vscode": true,
    "restore_apps": false
  },
  "tags": ["업무", "개인", "부동산", "정산"],
  "templates": []
}
```

---

## 스냅샷 구조 (snapshots/<id>.json)

```json
{
  "id": "20240115-143022",
  "title": "feature/auth 작업 중",
  "created_at": "2024-01-15T14:30:22",
  "root": "C:\\Projects\\my-app",
  "vscode_workspace": "",
  "note": "로그인 기능 구현 중...",
  "todos": ["API 연동 완료", "테스트 케이스 작성", "PR 제출"],
  "tags": ["업무"],
  "pinned": false,
  "archived": false,
  "recent_files": ["src/auth.py", "tests/test_auth.py"],
  "processes": [{"pid": 123, "name": "code.exe", "exe": "..."}],
  "running_apps": [{"name": "Code", "exe": "...", "title": "..."}]
}
```

---

## 의존성

| 패키지 | 용도 |
|--------|------|
| PySide6 | Qt6 GUI 프레임워크 |
| psutil | 프로세스/시스템 정보 |
| (표준 라이브러리) | ctypes, subprocess, json, logging |

---

## Windows 전용 API 사용

| API | 용도 | 파일 |
|-----|------|------|
| `user32.RegisterHotKey` | 글로벌 핫키 등록 | ctxsnap_win.py |
| `user32.EnumWindows` | 실행 중 윈도우 열거 | ctxsnap/utils.py |
| `os.startfile` | 폴더/파일 열기 | ctxsnap/restore.py |

---

## 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+N` | 새 스냅샷 |
| `Ctrl+E` | 선택된 스냅샷 편집 |
| `Ctrl+R` / `Enter` | 선택된 스냅샷 복원 |
| `Delete` | 선택된 스냅샷 삭제 |
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+P` | 핀 토글 |
| `Ctrl+,` | 설정 열기 |
| `Escape` | 검색 지우기 |
| `Ctrl+Alt+S` | Quick Snapshot (글로벌) |

---

## 테스트 가이드

현재 자동 테스트 없음. 수동 테스트 항목:

1. **스냅샷 CRUD**: 생성/조회/수정/삭제
2. **복원 동작**: 폴더/터미널/VSCode 열기
3. **핫키**: Ctrl+Alt+S 동작
4. **필터/검색**: 태그, 텍스트 검색
5. **설정**: 변경 저장 및 적용
6. **백업**: 내보내기/가져오기

---

## 알려진 이슈 및 제한

- Windows 전용 (Linux/macOS 미지원)
- VSCode 연동은 `code` 명령이 PATH에 필요
- 대용량 폴더 스캔 시 성능 저하 가능

---

## 코드 품질 개선 (최신)

| 개선 항목 | 내용 |
|----------|------|
| 원자적 쓰기 | `save_json()`이 `os.replace()` 사용 |
| ID 충돌 방지 | `gen_id()`에 랜덤 접미사 추가 |
| 예외 처리 | 핫키 필터, 삭제, JSON 파싱 등 |
| i18n 완성 | 23개 키 추가, 하드코딩 제거 |
| Git 안전성 | subprocess에 5초 타임아웃 |

---

## 향후 계획

- [ ] 크로스 플랫폼 지원
- [ ] 팀 협업 기능
- [ ] 클라우드 동기화
- [ ] 자동화 테스트 추가
