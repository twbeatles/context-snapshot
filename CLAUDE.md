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
├── pyrightconfig.json
├── .editorconfig
├── .gitattributes
├── README.md
├── README.en.md
├── PROJECT_STRUCTURE_ANALYSIS.md
├── gpt.md
├── CLAUDE.md
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
- `ctxsnap/storage.py`는 제거된 레거시 파일입니다.
- `ui/main_window.py`는 오케스트레이션 중심이며 주요 기능은 section mixin으로 분리되어 있습니다.

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
- `settings.default_root`: 자동화 기준 루트, Settings에서만 변경
- `settings.sync`: `provider`, `local_root`, `auto_interval_min`, `last_cursor`
- `settings.security`: `dpapi_enabled`, `encrypt_*`
- `settings.search`: `enable_field_query`, `saved_queries`
- `settings.restore_profiles`: 복원 프리셋 목록
- `index.tombstones`: 삭제 전파용 tombstone 목록(`id`, `deleted_at`), 30일 유지
- `snapshot.schema_version=2`, `rev`, `updated_at`
- `snapshot.git_state`: `branch`, `sha`, `dirty`, `changed`, `staged`, `untracked`
- `snapshot.sensitive`: DPAPI envelope (`enc=dpapi`, `v`, `blob`)

운영 규칙:

- DPAPI 스냅샷의 복호화된 민감 텍스트는 `index.search_blob`에 저장하지 않는다.
- 메타 수정/자동 보관/최근 파일 백그라운드 갱신은 raw snapshot 기준으로 저장해서 민감 평문이 다시 파일에 쓰이지 않게 한다.
- 복호화 실패 시 `_security_error`를 유지하고 UI(상세 패널, 복원 미리보기)에서 경고를 표시한다.
- 스냅샷 export/주간 보고서는 민감 데이터가 있으면 `Full export` 또는 `Redacted export`를 먼저 선택해야 한다.
- 메인 검색창 옆 드롭다운은 `settings.search.saved_queries`를 바로 적용하는 읽기 전용 진입점이다.

## 기능 플래그

기본값은 모두 `false`.

- `sync_enabled`: 동기화 메뉴/타이머/엔진 활성화
- `security_enabled`: 스냅샷 민감필드 암호화 흐름 활성화
- `advanced_search_enabled`: `tag:`, `root:`, `todo:` 쿼리 파서 활성화
- `restore_profiles_enabled`: 복원 프로필 UI/적용 활성화

## 테스트 / 타입검사 / CI

- 로컬 실행: `python ctxsnap_win.py`
- 로컬 테스트: `pytest -q`
- 로컬 타입검사: `pyright`
- CI: GitHub Actions(`.github/workflows/ci.yml`)에서 Windows 기준 `pyright` + `pytest` 실행

## 빌드

```bash
python -m PyInstaller ctxsnap_win.spec
```

- `ctxsnap_win.spec`는 section/dialogs 모듈을 `hiddenimports`에 명시해 분할 구조 빌드 안정성을 높입니다.

## 저장소 정합성 가드

- `pyrightconfig.json`: Pylance/pyright 공통 타입 검사 설정 (Windows, Python 3.11)
- `.editorconfig`: UTF-8, CRLF, final newline, trailing whitespace 정책
- `.gitattributes`: 텍스트 파일 EOL 정규화 정책
- `.gitignore`: 빌드 산출물/캐시/로컬 환경 파일 제외

## 작업 시 유의사항

- 사용자 노출 문자열은 `tr()` 경유(i18n)
- 신규 설정 키는 `migrate_settings()` 기본값/마이그레이션에 반영
- 스냅샷/인덱스/설정 동시 변경 경로는 롤백 보장
- 대용량 스캔/작업은 UI 스레드 차단 금지(워커/백그라운드 처리)
