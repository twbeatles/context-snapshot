# CtxSnap 프로젝트 구조 정합성 분석 (업데이트)

- 작성일: 2026-02-27
- 기준 코드: `main` 워크트리 최신 상태
- 참조 문서: `README.md`, `README.en.md`, `CLAUDE.md`, `gpt.md`

## 1. 결론 요약

코드베이스는 기존 단일 `main_window.py` 집중 구조에서 다음과 같이 분리/고도화된 상태입니다.

- 서비스 레이어 도입: `ctxsnap/services/*`
- UI 로직 분할: `ctxsnap/ui/main_window_sections/*`
- 동기화 엔진 도입: `ctxsnap/core/sync/*`
- DPAPI 보안 계층 도입: `ctxsnap/core/security.py`
- 검색 고도화: 필드 쿼리(`tag:`, `root:`, `todo:`)
- 테스트/CI 도입: `tests/*`, `.github/workflows/ci.yml`
- 레거시 `ctxsnap/storage.py` 제거

즉, 초기 분석 문서의 P0/P1/P2 핵심 방향이 코드에 대부분 반영되었습니다.

## 2. 최신 폴더 구조

```text
context-snapshot/
├─ ctxsnap_win.py
├─ ctxsnap_win.spec
├─ requirements.txt
├─ requirements-dev.txt
├─ README.md
├─ README.en.md
├─ CLAUDE.md
├─ gpt.md
├─ PROJECT_STRUCTURE_ANALYSIS.md
├─ .github/workflows/ci.yml
├─ tests/
│  ├─ test_migration.py
│  ├─ test_sync_engine.py
│  ├─ test_security_service.py
│  ├─ test_backup_encryption.py
│  └─ test_search_service.py
└─ ctxsnap/
   ├─ app_storage.py
   ├─ constants.py
   ├─ i18n.py
   ├─ restore.py
   ├─ utils.py
   ├─ core/
   │  ├─ logging.py
   │  ├─ worker.py
   │  ├─ security.py
   │  └─ sync/
   │     ├─ base.py
   │     ├─ engine.py
   │     └─ providers/
   │        ├─ local.py
   │        └─ cloud_stub.py
   ├─ services/
   │  ├─ snapshot_service.py
   │  ├─ restore_service.py
   │  ├─ backup_service.py
   │  └─ search_service.py
   └─ ui/
      ├─ main_window.py
      ├─ main_window_sections/
      │  ├─ automation.py
      │  ├─ list_view.py
      │  ├─ snapshot_crud.py
      │  ├─ settings_backup.py
      │  └─ restore_actions.py
      ├─ dialogs/
      ├─ hotkey.py
      ├─ models.py
      └─ styles.py
```

## 3. 런타임 아키텍처

### 3.1 시작/초기화

1. `ctxsnap_win.py`에서 Qt 앱/트레이/핫키 초기화
2. `ensure_storage()`로 저장소 및 기본 파일 생성
3. `MainWindow`에서 서비스/엔진 생성
4. 설정 마이그레이션 후 타이머/메뉴/목록 초기화

### 3.2 UI 책임 분리

- `main_window.py`: 오케스트레이션
- `main_window_sections/automation.py`: 자동 스냅샷/백업/동기화/보관
- `main_window_sections/list_view.py`: 검색/필터/페이지네이션/목록
- `main_window_sections/snapshot_crud.py`: 스냅샷 생성/편집/저장/삭제
- `main_window_sections/settings_backup.py`: 설정 적용 + 백업 import/export 적용
- `main_window_sections/restore_actions.py`: 복원/내보내기/히스토리/비교

### 3.3 서비스 계층

- `SnapshotService`: snapshot/index 마이그레이션 및 메타 갱신
- `RestoreService`: 복원 기본값/프로필 처리
- `BackupService`: 백업 내보내기/가져오기 도메인 처리
- `SearchService`: 일반 검색 + 필드 쿼리 파싱/매칭

### 3.4 동기화/보안

- `SyncEngine`: pull/merge/push + 충돌 큐 기록
- `LocalSyncProvider`: 로컬 파일 기반 provider
- `CloudStubSyncProvider`: 클라우드 스텁 provider
- `SecurityService`: Windows DPAPI 암복호화(선택형)

## 4. 저장 포맷/스키마

저장 루트: `%APPDATA%\ctxsnap\`

- `settings.json`: `schema_version=2`, `dev_flags`, `sync`, `security`, `search`, `restore_profiles`
- `index.json`: `schema_version`, `rev`, `updated_at`, `search_meta`, `snapshots`
- `snapshots/<id>.json`: `schema_version`, `rev`, `updated_at`, 확장 `git_state`, `sensitive`
- `sync_conflicts.json`: 동기화 충돌 큐
- `sync_state.json`: provider/cursor/last_sync 상태

DPAPI envelope 포맷:

```json
{"enc":"dpapi","v":1,"blob":"<base64>"}
```

## 5. 정합성 체크 결과

### 5.1 문서 ↔ 코드

- `README.md/README.en.md`의 기능/설정/저장경로 설명을 최신 구조에 맞춰 갱신 필요(이번 반영)
- `CLAUDE.md/gpt.md`의 구형 구조(`storage.py`, 단일 main_window 집중) 설명 갱신 필요(이번 반영)
- `PROJECT_STRUCTURE_ANALYSIS.md` 자체도 최신 상태 기준으로 재작성 필요(이번 반영)

### 5.2 빌드 스펙 ↔ 코드

- `ctxsnap_win.spec`는 동작 가능하나, 모듈 분할 이후 hiddenimports를 명시하면 빌드 안정성 향상 여지 있음(이번 반영)

### 5.3 테스트/CI

- `pytest` 테스트 세트 존재
- GitHub Actions CI에서 Windows 환경 테스트 실행

## 6. 남은 개선 여지

- cloud provider 실연동(`cloud_stub` 대체)
- 충돌 큐 UI(설정/도구 메뉴에서 직접 조회/해결)
- 저장 쿼리(`search.saved_queries`) 관리 UX 개선
- 보안 기능 활성화 시 운영 가이드/오류복구 UX 강화

## 7. 운영 권장사항

- 기능 플래그 기본값은 `false` 유지
- 파괴적 연산 전 안전 백업 선행
- 신규 설정 키 추가 시 반드시 `migrate_settings()` 동기화
- 사용자 노출 문자열은 `tr()` 경유 원칙 유지
