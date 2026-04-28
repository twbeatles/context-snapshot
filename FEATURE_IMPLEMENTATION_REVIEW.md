# CtxSnap Feature Implementation Review

- 작성일: 2026-04-28
- 상태: 구현 반영 완료
- 확인 명령:
  - `python -m pytest -q` -> 31 passed
  - `python -m pyright` -> 0 errors, 0 warnings

## 반영된 개선 사항

- DPAPI encrypted snapshot의 metadata-only 저장 경로에서 기존 `sensitive` envelope를 보존하도록 수정했다.
- 자유 검색은 `index.search_blob`에 공개 캐시가 있어도 runtime decrypted snapshot 내용을 함께 검색한다.
- Git 감지는 `.git` 직접 검사 대신 `git -C` discovery를 사용하며 branch/sha/dirty/changed/staged/untracked 상태를 비교한다.
- Quick Snapshot은 최신 스냅샷의 root/tags를 기본값으로 사용한다.
- TODO capture가 꺼져 있으면 TODO 필수 검증과 입력 영역을 비활성화한다.
- Restore History는 더블클릭 또는 Restore Again으로 이전 복원을 재실행할 수 있다.
- Redacted export는 note/TODO/process/app뿐 아니라 root/workspace/recent files/Git state도 제거한다.
- Backup import는 `default_root`가 다를 때 가져온 값 적용 또는 현재 값 유지를 선택한다.
- 자동 백업 실패 시 성공 메시지와 `auto_backup_last` 갱신을 하지 않는다.
- backup/sync/import snapshot id는 basename-safe 검증을 통과해야 한다.
- sync conflict는 local/remote payload를 `sync_conflicts.json`에 함께 보존하고, remote payload를 local fallback으로 자동 덮어쓰지 않는다.
- Settings에 기존 plaintext 스냅샷 수동 암호화 migration을 추가했고, 실행 전 안전 백업을 생성한다.
- 신규/Reset Defaults 설정은 언어별 기본 태그를 사용하며 기존 사용자 태그를 migration에서 덮어쓰지 않는다.

## 문서와 패키징 정합성

- `README.md`, `README.en.md`, `CLAUDE.md`, `gpt.md`, `PROJECT_STRUCTURE_ANALYSIS.md`를 현재 구현 기준으로 갱신했다.
- `ctxsnap_win.spec`는 신규 기능이 기존 hidden-import 모듈 내부에 있어 변경이 필요하지 않음을 확인했다.
- `.gitignore`는 PyInstaller/Inno Setup 및 릴리스 산출물을 더 넓게 제외하도록 보강했다.

## 남은 개선 여지

- Sync conflict는 read-only inspection까지 구현되었고, full merge/resolution editor는 추후 과제로 남았다.
- `cloud_stub` 외 실제 cloud provider 연동은 아직 미구현이다.
- Redacted export는 강한 익명화로 바뀌었지만, export 전 미리보기/요약 UX는 추후 개선 가능하다.
