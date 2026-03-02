<<<<<<< HEAD
# CLAUDE.md - CtxSnap 프로젝트 가이드

> AI 어시스턴트가 이 저장소에서 작업할 때 참조하는 최신 요약 문서입니다.

## 프로젝트 개요

**CtxSnap**은 Windows 전용(PySide6) 작업 컨텍스트 스냅샷 앱입니다.

- 스냅샷 저장: root/workspace/note/todos/tags/recent files/processes/running apps
- 복원 실행: 폴더/터미널/VSCode/앱 복원 + 이력 기록
- 자동화: 주기 스냅샷, Git 변경 감지, 자동 백업/보관
- 확장: 서비스 레이어, 동기화 엔진, DPAPI 보안, 필드 검색, 복원 프로필

## 디렉토리 구조 (최신)

```text
context-snapshot/
├── ctxsnap_win.py
├── ctxsnap_win.spec
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── README.en.md
├── PROJECT_STRUCTURE_ANALYSIS.md
├── ctxsnap/
│   ├── app_storage.py
│   ├── constants.py
│   ├── i18n.py
│   ├── restore.py
│   ├── utils.py
│   ├── core/
│   │   ├── logging.py
│   │   ├── worker.py
│   │   ├── security.py
│   │   └── sync/
│   │       ├── base.py
│   │       ├── engine.py
│   │       └── providers/
│   │           ├── local.py
│   │           └── cloud_stub.py
│   ├── services/
│   │   ├── snapshot_service.py
│   │   ├── restore_service.py
│   │   ├── backup_service.py
│   │   └── search_service.py
│   └── ui/
│       ├── main_window.py
│       ├── main_window_sections/
│       │   ├── automation.py
│       │   ├── list_view.py
│       │   ├── snapshot_crud.py
│       │   ├── settings_backup.py
│       │   └── restore_actions.py
│       ├── dialogs/
│       ├── hotkey.py
│       ├── models.py
│       └── styles.py
├── tests/
│   ├── test_migration.py
│   ├── test_sync_engine.py
│   ├── test_security_service.py
│   ├── test_backup_encryption.py
│   └── test_search_service.py
└── .github/workflows/ci.yml
```

참고:
- `ctxsnap/storage.py`는 제거됨(legacy).
- `ui/main_window.py`는 오케스트레이션 중심, 실제 기능은 section mixin으로 분리됨.

## 런타임 아키텍처

1. `ctxsnap_win.py`에서 Qt 앱/트레이/핫키 초기화
2. `ensure_storage()`로 `%APPDATA%\ctxsnap` 저장소 보장
3. `MainWindow`에서 서비스 초기화:
   - `SnapshotService`, `RestoreService`, `BackupService`, `SearchService`
   - `SecurityService`, `SyncEngine`
4. UI 액션은 section 믹스인 메서드에서 처리:
   - 자동화, 검색/리스트, 스냅샷 CRUD, 설정/백업, 복원 액션
5. 저장 경로 실패 시 롤백 정책 적용

## 저장 데이터 모델

루트 경로: `%APPDATA%\ctxsnap\`

- `settings.json`
- `index.json`
- `snapshots/<id>.json`
- `restore_history.json`
- `sync_conflicts.json`
- `sync_state.json`
- `logs/ctxsnap.log`

핵심 필드:

- `settings.schema_version=2`
- `settings.dev_flags`: `sync_enabled`, `security_enabled`, `advanced_search_enabled`, `restore_profiles_enabled`
- `settings.sync`: `provider`, `local_root`, `auto_interval_min`, `last_cursor`
- `settings.security`: `dpapi_enabled`, `encrypt_*`
- `settings.search`: `enable_field_query`, `saved_queries`
- `settings.restore_profiles`: 복원 프리셋 목록
- `snapshot.schema_version=2`, `rev`, `updated_at`
- `snapshot.git_state`: `branch`, `sha`, `dirty`, `changed`, `staged`, `untracked`
- `snapshot.sensitive`: DPAPI envelope (`enc=dpapi`, `v`, `blob`)

## 기능 플래그

기본값은 모두 `false`.

- `sync_enabled`: 동기화 메뉴/타이머/엔진 활성화
- `security_enabled`: 스냅샷 민감필드 암호화 흐름 활성화
- `advanced_search_enabled`: `tag:`, `root:`, `todo:` 쿼리 파서 활성화
- `restore_profiles_enabled`: 복원 프로필 UI/적용 활성화

## 테스트 / CI

- 로컬: `pytest -q`
- 의존성: `requirements.txt` + `requirements-dev.txt`
- CI: GitHub Actions(`.github/workflows/ci.yml`)에서 Windows 테스트 수행

## 빌드

```bash
python -m PyInstaller ctxsnap_win.spec
```

## 작업 시 유의사항

- 사용자 노출 문자열은 `tr()` 경유(i18n)
- 신규 설정 키는 `migrate_settings()` 기본값/마이그레이션에 반영
- 스냅샷/인덱스/설정 동시 변경 경로는 롤백 보장
- 대용량 스캔/작업은 UI 스레드 차단 금지(워커/백그라운드 처리)
=======
# CLAUDE.md - CtxSnap 프로젝트 가이드

> AI 어시스턴트가 이 프로젝트를 이해하고 작업할 때 참고하는 문서입니다.

## 프로젝트 개요

**CtxSnap**은 PySide6 기반 Windows 전용 작업 컨텍스트 스냅샷 도구입니다. 현재 작업 맥락(폴더, 메모, TODO, 최근 파일, 실행 중 프로세스 등)을 저장하고 나중에 빠르게 복원할 수 있도록 돕습니다.

### 핵심 가치
- 작업 전환 시 "어디까지 했지?" 문제 해결
- TODO 3개 필수 입력으로 **다음 행동 명확화**
- 폴더/터미널/VSCode 한 번에 복원

---

## 디렉토리 구조

```
context-snapshot-main/
├── ctxsnap_win.py          # 메인 애플리케이션 진입점
├── ctxsnap/                # 핵심 패키지
│   ├── __init__.py
│   ├── app_storage.py      # 설정/스냅샷 저장 로직
│   ├── constants.py        # 상수 정의
│   ├── i18n.py             # 다국어 처리
│   ├── restore.py          # 복원 헬퍼
│   ├── utils.py            # 유틸리티 함수
│   ├── core/               # 핵심 로직 (로깅, 워커)
│   │   ├── logging.py
│   │   └── worker.py
│   └── ui/                 # UI 컴포넌트
│       ├── dialogs/        # 다이얼로그 모음
│       ├── main_window.py  # 메인 윈도우
│       ├── models.py       # 데이터 모델
│       └── styles.py       # 스타일시트/테마
├── assets/                 # 아이콘/이미지
├── installer/              # Inno Setup 설치 스크립트
├── scripts/                # 유틸리티 스크립트
├── README.md               # 한국어 사용자 문서
├── README.en.md            # 영어 사용자 문서
├── gpt.md                  # GPT용 프로젝트 노트
├── requirements.txt        # Python 의존성
└── ctxsnap_win.spec        # PyInstaller 빌드 스펙
```

---

## 데이터 저장 위치

```
%APPDATA%\ctxsnap\
├── snapshots/              # 개별 스냅샷 JSON 파일
│   └── <id>.json
├── index.json              # 스냅샷 인덱스 메타데이터
├── settings.json           # 앱 설정
├── restore_history.json    # 복원 히스토리
└── logs/
    └── ctxsnap.log         # 로테이팅 로그 파일
```

스냅샷 JSON의 주요 메타 필드:
- `source`: 수동/자동 생성 소스 (`auto_timer`, `auto_git`, ...)
- `trigger`: 자동 생성 트리거 (`timer`, `git_change`, ...)
- `git_state`: 자동 스냅샷 시점 Git 상태 (`branch`, `sha`)
- `auto_fingerprint`: 자동 스냅샷 dedup 해시

복원 기록 JSON(`restore_history.json`) 추가 필드:
- `running_apps_failed_count`: 앱 복원 실패 개수 (정수)

---

## 핵심 모듈 설명

### ctxsnap/ui/main_window.py (UI 메인)
| 클래스/함수 | 역할 |
|------------|------|
| `MainWindow` | 메인 UI 윈도우 (검색, 필터, 스냅샷 리스트, 상세 뷰) |
| `SnapshotListModel` | 스냅샷 목록 필터링/표시 모델 |
| `git_title_suggestion()` | Git 브랜치 기반 제목 추천 |

### ctxsnap/ui/dialogs/
| 파일 | 역할 |
|------|------|
| `snapshot.py` | 스냅샷 생성/편집 (`SnapshotDialog`) |
| `settings.py` | 설정창 (`SettingsDialog`) |
| `onboarding.py` | 첫 실행 가이드 (`OnboardingDialog`) |
| `history.py` | 복원 기록 (`RestoreHistoryDialog`) |
| `restore.py` | 복원 미리보기 (`RestorePreviewDialog`) |

### ctxsnap/core/worker.py
| 클래스 | 역할 |
|--------|------|
| `RecentFilesWorker` | 백그라운드 최근 파일 스캔 (QRunnable) |

### ctxsnap/hotkey.py (in ui/)
| 클래스/함수 | 역할 |
|-------------|------|
| `HotkeyFilter` | 글로벌 단축키 이벤트 필터 |
| `register_hotkey` | Windows API 핫키 등록 |


### ctxsnap/utils.py
| 함수 | 역할 |
|------|------|
| `recent_files_under()` | 루트 폴더 아래 최근 수정 파일 스캔 |
| `list_processes_filtered()` | 키워드 기반 프로세스 필터링 |
| `list_running_apps()` | 현재 실행 중인 Windows 앱 목록 |
| `restore_running_apps()` | 저장된 앱 목록 복원 실행 |
| `build_search_blob()` | 검색용 인덱스 문자열 생성 |

### ctxsnap/app_storage.py
| 함수 | 역할 |
|------|------|
| `ensure_storage()` | 초기 저장소 디렉토리/파일 생성 |
| `migrate_settings()` | 이전 버전 설정 마이그레이션 |
| `migrate_snapshot()` | 이전 버전 스냅샷 마이그레이션 |
| `export_backup_to_file()` | 백업 파일 내보내기 |
| `import_backup_from_file()` | 백업 파일 가져오기 |
| `append_restore_history()` | 복원 히스토리 기록 |



---

## 주요 기능

1. **스냅샷 생성**: 제목, 루트 폴더, 메모, TODO 3개, 태그 저장
2. **복원**: 폴더/터미널/VSCode 열기 + 실행 중이던 앱 복원
3. **태그/고정(Pin)**: 태그 필터링, 중요 스냅샷 고정
4. **검색**: 제목/루트/태그/메모/TODO/프로세스 통합 검색
5. **글로벌 핫키**: Ctrl+Alt+S (설정 가능)로 빠른 스냅샷
6. **자동 스냅샷**: 주기적 또는 Git 변경 감지 기반 (확인 다이얼로그 없이 저장)
7. **템플릿**: 자주 쓰는 TODO/태그/메모 템플릿
8. **스냅샷 비교**: 두 스냅샷 차이 비교
10. **복원 기록**: 최근 복원 내역 확인 및 재실행
11. **온보딩 & 다국어**: 첫 사용자 가이드 및 한/영 지원
12. **트레이 종료 정책**: 창 닫기(X)는 트레이 최소화, 실제 종료는 Quit
13. **백업 가져오기 적용 방식**: `Apply now`는 즉시 적용, `Keep in dialog`는 저장 시 적용

---

## 개발 가이드

### 개발 환경 실행
```bash
pip install -r requirements.txt
python ctxsnap_win.py
```

### EXE 빌드 (PyInstaller)
```bash
python -m PyInstaller ctxsnap_win.spec
# 결과: dist\CtxSnap\CtxSnap.exe
```

### 설치 프로그램 빌드 (Inno Setup)
1. EXE 먼저 빌드
2. `installer/ctxsnap.iss`를 Inno Setup Compiler로 열고 빌드

---

## 코딩 규칙

### Python 스타일
- **타입 힌트** 사용 (`from __future__ import annotations`)
- **데이터클래스** 활용 (`@dataclass`)
- **예외 처리**: 모든 파일/프로세스 작업에 try-except 사용

### 성능 고려사항
- 파일 시스템 스캔은 **시간/개수 제한** 적용 (`scan_limit`, `scan_seconds`)
- 무거운 작업은 **QRunnable/QThreadPool** 사용
- 대량 스냅샷은 **페이지네이션** 적용

### 보안/프라이버시
- 민감한 데이터 기본 저장 금지 (캡처 토글 존중)
- 최근 파일/프로세스 저장 제외 옵션 제공

### 코드 구성
- 공통 로직은 `ctxsnap/utils.py`로 분리
- UI 응답성 유지 (Heavy 작업은 백그라운드 처리)
- 신규 설정 키는 `migrate_settings()`에 **기본값 추가**
- 상수는 `ctxsnap/constants.py`에서만 정의 (`APP_NAME` 등)
- i18n: 모든 사용자 메시지는 `tr()` 함수 사용
- 파일 쓰기: `os.replace()` 사용으로 원자적 처리
- subprocess: 타임아웃 필수 (예: `timeout=5`)

---

## 설정 키 (settings.json)

| 키 | 설명 | 기본값 |
|----|------|--------|
| `default_root` | 기본 루트 폴더 | `%USERPROFILE%` |
| `hotkey.enabled` | 글로벌 핫키 활성화 | `true` |
| `hotkey.ctrl/alt/shift/vk` | 핫키 조합 | `Ctrl+Alt+S` |
| `recent_files_limit` | 최근 파일 수집 개수 | `30` |
| `recent_files_exclude` | 제외 디렉토리 | `[".git", "node_modules"]` |
| `process_keywords` | 프로세스 필터 키워드 | `["code", "chrome", ...]` |
| `auto_snapshot_minutes` | 자동 스냅샷 주기(분) | `0` (비활성) |
| `auto_snapshot_on_git_change` | Git 변경 시 자동 스냅샷 | `false` |
| `restore.open_folder/terminal/vscode` | 복원 동작 설정 | 각각 `true` |
| `restore.open_running_apps` | 복원 시 앱 실행 | `false` |
| `tags` | 사용자 정의 태그 목록 | `["업무", "개인", ...]` |

---

## 테스트

> 현재 자동화된 테스트 없음. 수동 테스트 권장.

### 수동 테스트 체크리스트
1. 스냅샷 생성 및 저장 확인
2. 스냅샷 복원 (폴더/터미널/VSCode)
3. 글로벌 핫키 동작
4. 태그 필터링
5. 검색 기능
6. 설정 변경 및 저장
7. 백업/복원 기능

---

## 의존성

```
PySide6>=6.0.0
psutil>=5.9.0
python-dotenv (선택)
```

---

## 알려진 제한사항

- Windows 전용 (ctypes.windll 사용)
- VSCode `code` 명령이 PATH에 있어야 VSCode 연동 작동
- 대용량 프로젝트에서 파일 스캔이 느릴 수 있음

---

## 코드 품질 개선 (최신)

- **원자적 파일 쓰기**: `save_json()`이 `os.replace()` 사용
- **ID 충돌 방지**: `gen_id()`에 랜덤 접미사 추가
- **예외 처리 강화**: 핫키 필터, 삭제 작업 등
- **i18n 완성도**: 23개 키 추가, 하드코딩 문자열 제거
- **Git 타임아웃**: subprocess 호출에 5초 타임아웃 적용
- **UI/UX 리팩토링**: `SnapshotItemDelegate` 도입으로 카드형 리스트 구현, `QStackedWidget` 기반 Empty State 적용, 상세 뷰 HTML 렌더링 개선
- **디자인 시스템**: QSS 스타일시트 전면 개편으로 모던한 다크 테마 및 컴포넌트 스타일 적용

---

## 향후 개선 아이디어

- [ ] 팀/협업 기능 (스냅샷 공유)
- [ ] Slack/Notion 연동
- [ ] 스냅샷 암호화
>>>>>>> 263e8f0 (feat(ui): refactor UI/UX with modern card design, HTML delegate, and empty state)
