Version: 0.6.12-review-s04.2
# S04 Storage + Utilities/Client Review (Review-only pass)

## 1) Executive summary

This merged Step 4 review covered runner storage/lifecycle/persistence/housekeeping/state/stats plus utilities, client layer, API contract surface, and example usage. The implementation is generally modular and testable, but there are several correctness and resilience gaps around housekeeping deletion consistency, purge reporting accuracy, and client-side zip extraction safety controls. No fixes were applied in this run.

## 2) Files reviewed

### Section A scope (storage/lifecycle/persistence/housekeeping)
- `pythonista_job_runner/app/runner/store.py`
- `pythonista_job_runner/app/runner/store_index.py`
- `pythonista_job_runner/app/runner/store_lifecycle.py`
- `pythonista_job_runner/app/runner/store_persistence.py`
- `pythonista_job_runner/app/runner/housekeeping.py`
- `pythonista_job_runner/app/runner/state.py`
- `pythonista_job_runner/app/runner/stats.py`

### Section B scope (utilities/client/contract/example)
- `pythonista_job_runner/app/utils.py`
- `pythonista_job_runner/app/pythonista_client.py`
- `pythonista_job_runner/examples/pythonista_run_job.py`
- `pythonista_job_runner/api/openapi.json`

### Directly related tests reviewed
- `pythonista_job_runner/tests/test_job_store_registry.py`
- `pythonista_job_runner/tests/test_backup_pause_resume.py`
- `pythonista_job_runner/tests/test_api_contract.py`
- `pythonista_job_runner/tests/test_pythonista_client.py`
- `pythonista_job_runner/tests/test_utils_zip_extract.py`

### Tiny nearby context helper read
- `pythonista_job_runner/app/runner_core.py` (only for job-user fallback intent referenced by lifecycle/deps interactions)

## 3) Validation context

Baseline full-repo validations are already recorded in `reviews/code-review/2026-03-08/FULL_CODE_REVIEW_PLAN.md` and were not repeated.

Commands executed for this merged Step 4 review:
- `pytest -q pythonista_job_runner/tests/test_job_store_registry.py pythonista_job_runner/tests/test_backup_pause_resume.py pythonista_job_runner/tests/test_api_contract.py pythonista_job_runner/tests/test_pythonista_client.py pythonista_job_runner/tests/test_utils_zip_extract.py` (pass: 23 passed)
- `python -m py_compile pythonista_job_runner/app/runner/store.py pythonista_job_runner/app/runner/store_index.py pythonista_job_runner/app/runner/store_lifecycle.py pythonista_job_runner/app/runner/store_persistence.py pythonista_job_runner/app/runner/housekeeping.py pythonista_job_runner/app/runner/state.py pythonista_job_runner/app/runner/stats.py pythonista_job_runner/app/utils.py pythonista_job_runner/app/pythonista_client.py pythonista_job_runner/examples/pythonista_run_job.py` (pass)
- `python - <<'PY' ...` inspection of OpenAPI path/method inventory for contract/client alignment context

No production code edits were made.

## 4) Section A: runner storage, lifecycle, persistence, and housekeeping findings

### S04-H-01
- **Severity:** High
- **Title:** Section A — Low-disk cleanup can orphan in-memory job entries when `status.json` job_id mismatches directory
- **File and region:** `pythonista_job_runner/app/runner/housekeeping.py`, `ensure_min_free_space` candidate job-id derivation and fallback discard path.
- **Description of the issue:** Low-disk cleanup derives `job_id` from `status.json` (`data.get("job_id")`) instead of the authoritative directory name. In fallback cleanup, it deletes directory `p` and then discards registry entry by that potentially mismatched id.
- **Why it matters:** If status metadata is inconsistent/corrupt, cleanup can remove on-disk artefacts for one job while leaving stale in-memory entries for the real directory-backed job, causing state drift and inconsistent API behavior.
- **Evidence or reasoning:** Candidate logic uses `job_id = str(data.get("job_id") or p.name)`; fallback path executes `shutil.rmtree(p)` then `JobStore.for_runner(runner).discard_job_id(job_id)`. This differs from persistence logic which explicitly treats directory name as authoritative job id.
- **Recommended narrow fix:** In housekeeping cleanup paths, use `p.name` as authoritative key for delete/discard; keep status `job_id` only as diagnostic metadata.
- **Tests to add or update:** Add a housekeeping-focused test with a directory whose `status.json` claims a different job_id and assert cleanup removes both disk artefacts and corresponding in-memory registry entry keyed by directory name.

### S04-M-01
- **Severity:** Medium
- **Title:** Section A — Purge reports jobs as deleted even when deletion operation returns false
- **File and region:** `pythonista_job_runner/app/runner/store_lifecycle.py`, `purge_jobs` loop building `deleted` list.
- **Description of the issue:** `purge_jobs` appends `job_id` to `deleted` after calling `delete_job(...)` without checking its boolean return value.
- **Why it matters:** API/reporting can claim deletion success for jobs that were not actually deleted (race conditions or state changes), reducing operator trust and making cleanup audits misleading.
- **Evidence or reasoning:** In non-dry-run path, code calls `self.delete_job(job_id, actor=actor)` and unconditionally `deleted.append(job_id)` unless exception occurs.
- **Recommended narrow fix:** Capture and check return value; append only when `True`, and optionally track skipped/failed IDs separately.
- **Tests to add or update:** Add a test forcing `delete_job` to return `False` for one candidate and assert purge response reflects non-deletion accurately.

### S04-L-01
- **Severity:** Low
- **Title:** Section A — Backup pause test validates method presence by source text, not runtime behavior
- **File and region:** `pythonista_job_runner/tests/test_backup_pause_resume.py`, `test_runner_core_contains_pause_restore_methods`.
- **Description of the issue:** One backup-related test asserts string presence in `runner_core.py` source text rather than validating callable runtime behavior/contract.
- **Why it matters:** Source-string tests are brittle and can pass despite behavior regressions (e.g., method semantics changed but names still present).
- **Evidence or reasoning:** Test reads file text and checks literal substrings for `def pause_for_backup`, `def resume_after_backup`, and `def pause_status`.
- **Recommended narrow fix:** Replace source-text assertion with behavior-level tests against `Runner` pause/resume/status transitions (without broadening to HTTP layer).
- **Tests to add or update:** Add direct unit test covering state transitions and returned payload shape for pause/resume/status methods.

## 5) Section B: utilities, client layer, API contract, and example-usage findings

### S04-H-02
- **Severity:** High
- **Title:** Section B — Client zip extraction lacks safety limits and uses unrestricted `extractall`
- **File and region:** `pythonista_job_runner/app/pythonista_client.py`, `RunnerClient.extract_result_zip`.
- **Description of the issue:** Client extraction uses `ZipFile.extractall` with no member-count, size, symlink, or total-uncompressed guardrails.
- **Why it matters:** Even if server-side controls exist, client-side extraction should still defend against oversized/malicious zip payloads (e.g., zip bombs or unexpectedly huge artefacts) to prevent local disk/memory exhaustion.
- **Evidence or reasoning:** `extract_result_zip` directly opens zip and calls `zf.extractall(dst)`. In the same codebase, `utils.safe_extract_zip_bytes` already implements explicit extraction guardrails and can be reused/adapted for safer behavior.
- **Recommended narrow fix:** Replace direct `extractall` with a guarded extraction routine (reusing safe extraction limits/patterns from `utils`) and expose optional client-side limits.
- **Tests to add or update:** Add client tests for oversized/member-heavy result archives that should fail safely, plus a normal archive success case under limits.

### S04-M-02
- **Severity:** Medium
- **Title:** Section B — API contract tests are path-presence heavy and do not guard key schema/shape expectations used by client
- **File and region:** `pythonista_job_runner/tests/test_api_contract.py`.
- **Description of the issue:** Contract tests primarily verify route existence and selected response-code presence, but do not assert important response schema details consumed by `RunnerClient` (`RunAcceptedResponse` fields, job payload shape, tail/status structure).
- **Why it matters:** Response-shape drift can break client workflows while contract tests still pass, reducing usefulness of contract guardrails.
- **Evidence or reasoning:** Current tests check expected path set and selected response status codes/security scheme; they do not validate schema properties required by client parsing (`job_id`, `tail_url`, `result_url`, `jobs_url`, etc.).
- **Recommended narrow fix:** Extend contract tests to assert required schema fields and critical response object structure for `/run`, `/job/{job_id}.json`, and `/tail/{job_id}.json`.
- **Tests to add or update:** Add assertions against OpenAPI component schemas and required field lists used directly by `RunnerClient` and example flow.

## 6) Positive observations

- `JobStore` cleanly composes index/lifecycle/persistence responsibilities, which keeps mutable state operations auditable.
- Status persistence uses a temp-file + `os.replace` first strategy, reducing partial-write risk compared to direct writes.
- Utility zip extraction (`safe_extract_zip_bytes`) has strong guardrails for traversal/symlink/member-size/total-size checks and is backed by focused tests.
- `RunnerClient` centralizes request/response error normalization (`RunnerClientError`) and exposes a concise high-level flow (`run_zip_and_collect`) suitable for Pythonista usage.

## 7) Apply guidance

Recommended fix order for merged S04 apply-only pass:
1. **S04-H-01 first**: housekeeping delete/discard keying consistency (prevents state/disk drift under low-space pressure).
2. **S04-H-02 second**: add guarded client extraction limits (safety hardening for downloaded artefacts).
3. **S04-M-01 third**: correct purge result accounting to avoid false deletion reporting.
4. **S04-M-02 fourth**: harden contract tests around client-required response schemas.
5. **S04-L-01 last**: replace source-text backup test with behavior-level checks.

Keep apply work constrained to this merged Step 4 scope and directly related tests.
