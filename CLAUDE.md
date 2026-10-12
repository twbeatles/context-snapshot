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
├── FEATURE_IMPLEMENTATION_REVIEW.md
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
│   ├── test_automation_helpers.py
│   ├── test_dialog_behaviors.py
│   ├── test_git_helpers.py
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
- 신규 설정/Reset Defaults의 기본 태그는 언어별로 생성한다(`ko`: 업무/개인/부동산/정산, `en`: Work/Personal/Real Estate/Settlement). 기존 사용자 태그는 마이그레이션에서 덮어쓰지 않는다.
- `index.tombstones`: 삭제 전파용 tombstone 목록(`id`, `deleted_at`), 30일 유지
- `snapshot.schema_version=2`, `rev`, `updated_at`
- `snapshot.git_state`: `branch`, `sha`, `dirty`, `changed`, `staged`, `untracked`
- `snapshot.sensitive`: DPAPI envelope (`enc=dpapi`, `v`, `blob`)

운영 규칙:

- DPAPI 스냅샷의 복호화된 민감 텍스트는 `index.search_blob`에 저장하지 않는다.
- 메타 수정/자동 보관/최근 파일 백그라운드 갱신은 raw snapshot 기준으로 저장해서 민감 평문이 다시 파일에 쓰이지 않게 한다.
- raw encrypted snapshot을 metadata-only로 저장할 때는 기존 `sensitive` envelope를 반드시 보존한다.
- 복호화 실패 시 `_security_error`를 유지하고 UI(상세 패널, 복원 미리보기)에서 경고를 표시한다.
- 스냅샷 export/주간 보고서는 민감 데이터가 있으면 `Full export` 또는 `Redacted export`를 먼저 선택해야 한다. Redacted export는 note/TODO/process/app뿐 아니라 root/workspace/recent files/Git 상태도 제거한다.
- 기존 평문 스냅샷 암호화는 Settings의 수동 migration 버튼으로만 실행하며, 실행 전 안전 백업을 만든다.
- 메인 검색창 옆 드롭다운은 `settings.search.saved_queries`를 바로 적용하는 읽기 전용 진입점이다.
- Git 자동 스냅샷 감지는 `.git` 폴더 직접 검사 대신 `git -C` 기반으로 repository/worktree/subdirectory를 판별하고 branch/sha/dirty/changed/staged/untracked를 비교한다.
- Sync 충돌은 local/remote payload를 `sync_conflicts.json`에 함께 보존하며, 충돌한 remote payload를 local winner로 자동 덮어쓰지 않는다.
- 외부 backup/sync snapshot id는 basename-safe validator를 통과해야 하며 snapshots 디렉터리 밖 경로로 해석되면 거부한다.

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

<!-- SPECKIT-AGENT-GUIDE:START -->

## Spec Kit / Spec-Driven Development (AI 에이전트 필독)

> 이 블록은 GitHub Spec Kit 활성화 및 기능 명세 작업 결과를 AI 에이전트가 바로 쓰도록 정리한 안내입니다.
> 수정 시 마커 주석을 유지하세요. 스크립트/후속 세션이 이 구간을 갱신합니다.

### 이 저장소 상태

- **프로젝트**: `context-snapshot`
- **Spec Kit 초기화**: `.specify/ 있음`
- **에이전트 스킬**: Grok=True, Claude=True, Codex/Agy(.agents)=True
- **활성 기능**: 아직 `specs/` 기능 명세 없음 — `.specify/` 만 준비된 상태

### 에이전트가 먼저 읽을 파일

1. `.specify/` 및 `.grok/skills` / `.claude/skills` / `.agents/skills` 의 `speckit-*`
2. 기능 작업 시작 시 `/speckit-specify` 로 `specs/00N-...` 생성

### 권장 워크플로 (스킬 / 슬래시 커맨드)

| 단계 | 커맨드 (Grok/Claude 등) | 산출 |
|------|-------------------------|------|
| 원칙 | `/speckit-constitution` | `.specify/memory/constitution.md` |
| 명세 | `/speckit-specify` | `specs/<id>/spec.md` |
| 계획 | `/speckit-plan` | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` |
| 작업 | `/speckit-tasks` | `tasks.md` |
| 구현 | `/speckit-implement` | 코드 (tasks 순서) |
| 갭점검 | `/speckit-converge` | `tasks.md` 에 Phase Convergence **append-only** |

- Codex skills 모드: `$speckit-specify` 형태일 수 있음
- 스킬 파일: `.grok/skills/speckit-*/SKILL.md`, `.claude/skills/speckit-*/SKILL.md`

### 작업 규칙 (에이전트)

1. **새 기능/큰 변경 전** 활성 `spec.md`·`tasks.md` 를 읽고, 없으면 specify→plan→tasks 순으로 만든다.
2. **구현은 tasks.md 체크리스트**를 따른다. 완료 시 `- [ ]` → `- [x]`.
3. **`/speckit-converge` 는 tasks.md 를 rewrite 하지 않는다** — 잔여 갭만 하단 Phase 로 append.
4. brownfield 프로젝트는 상당 기능이 이미 있을 수 있다. 중복 구현 전에 코드·`[x]` 태스크를 확인한다.
5. 웹/데스크톱 패리티 등 **out-of-scope Assumptions** 는 새 feature 로 분리하는 것을 선호한다.
6. 기본 integration 은 **grok** 이며, 동일 레포에 claude / codex / agy 스킬도 multi-install 되어 있을 수 있다.

### 관련 링크

- Spec Kit: https://github.com/github/spec-kit
- 로컬 CLI: `specify` (uv tool, 버전은 `specify version`)

<!-- SPECKIT-AGENT-GUIDE:END -->
