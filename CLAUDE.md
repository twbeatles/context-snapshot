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
