Version: 0.6.12-review-plan.2
# Pythonista Job Runner Full Code Review Plan

Current location: `reviews/FULL_CODE_REVIEW_PLAN.md`

## Programme scope and operating rules

This repository-wide programme is split into slices. Each slice has two separate passes:

1. **Review-only pass**: identify and document issues; no production-code edits.
2. **Apply-only pass**: implement fixes strictly from the review file for that slice.

### Pass discipline
- Review-only passes must not edit production code.
- Apply-only passes must treat the corresponding review file as authoritative.
- Findings are severity-grouped: **Critical / High / Medium / Low**.
- Every finding must include: exact file, exact function/class/region, impact/risk, evidence/reasoning or repro, test impact, and narrowest safe fix direction.
- In this merged-step programme, **apply status is recorded in this plan file** rather than separate `*_apply.md` artefacts.

### Derived artefacts policy
Generated Web UI bundle files are treated as **derived artefacts**, not primary review targets:
- `pythonista_job_runner/app/webui.js`
- `pythonista_job_runner/app/webui.css`
- `pythonista_job_runner/app/webui.html`

Review generator/source files first, then validate generated outputs for drift.

## Baseline validations (run at start of programme)
- `pytest -q`
- `cd pythonista_job_runner && python app/webui_build.py --check`
- `cd pythonista_job_runner && node --check app/webui.js`

### Baseline validation results (this run)
- `pytest -q` → **pass** (221 passed).
- `cd pythonista_job_runner && python app/webui_build.py --check` → **pass**.
- `cd pythonista_job_runner && node --check app/webui.js` → **pass**.

### Blocking edits made to enable baseline validations
- None.

## Current merged-step structure

This is the final structure actually used by the review programme.

- **S01**: runner core
  - review file: `reviews/S01_runner_core_review.md`
  - apply status: recorded in this plan file
- **S02**: HTTP API, auth/helpers, audit, support bundle
  - review file: `reviews/S02_http_api_review.md`
  - apply status: recorded in this plan file
- **S03**: runner execution pipeline
  - review file: `reviews/S03_runner_execution_review.md`
  - apply status: recorded in this plan file
- **S04**: merged storage/lifecycle plus utilities/client/contract
  - review file: `reviews/S04_storage_utils_client_review.md`
  - apply status: recorded in this plan file
- **S05**: merged full Web UI source system
  - review file: `reviews/S05_webui_full_review.md`
  - apply status: recorded in this plan file
- **S06**: merged full custom integration
  - review file: `reviews/S06_custom_integration_full_review.md`
  - apply status: recorded in this plan file
- **S07**: add-on packaging, security, and repository automation
  - review file: `reviews/S07_packaging_security_review.md`
  - apply status: recorded in this plan file

### Mapping from the older unmerged layout
- old **S04** and old **S05** were merged into new **S04**
- old **S06**, old **S07**, and old **S08** were merged into new **S05**
- old **S09** and old **S10** were merged into new **S06**
- old **S11** became new **S07**

## S01 — Runner core
- **Scope files**:
  - `pythonista_job_runner/app/runner_core.py`
  - runner-core-specific tests:
    - `pythonista_job_runner/tests/test_runner_core.py`
    - `pythonista_job_runner/tests/test_runner_core_job.py`
    - `pythonista_job_runner/tests/test_runner_core_runner.py`
    - `pythonista_job_runner/tests/test_runner_core_options_and_helpers.py`
    - `pythonista_job_runner/tests/test_runner_core_outputs_and_load.py`
    - `pythonista_job_runner/tests/test_runner_core_process_and_notify.py`
    - `pythonista_job_runner/tests/test_runner_core_edge_cases.py`
    - `pythonista_job_runner/tests/test_runner_core_regressions_apply.py`
- **Review output**: `reviews/S01_runner_core_review.md`
- **Narrow validations**:
  - `pytest -q pythonista_job_runner/tests/test_runner_core.py`
  - `pytest -q pythonista_job_runner/tests/test_runner_core_*.py`

### S01 apply-only finding ledger

Helper-file scope note for Step 1 apply:
- `pythonista_job_runner/app/runner/housekeeping.py` is included narrowly to add stop-aware reaper-loop lifecycle support. `runner_core.py` alone is insufficient because its `_reaper` currently delegates to `housekeeping.reaper_loop`, which is an unconditional infinite loop with long sleep and no stop hook.

| Finding ID | Severity | Status | Planned action | Files expected to change | Narrow tests to run | Justification |
|---|---|---|---|---|---|---|
| S01-M-01 | Medium | fix_now | Replace per-event telemetry thread spawn with bounded queue + single worker thread and non-blocking enqueue/drop-on-full behaviour. | `pythonista_job_runner/app/runner_core.py`, `pythonista_job_runner/tests/test_runner_core_runner.py` | `pytest -q pythonista_job_runner/tests/test_runner_core_runner.py -k telemetry` | Medium reliability issue in core path; scoped and safe to fix now. |
| S01-M-02 | Medium | fix_now | Add lifecycle controls for reaper (`start_reaper` constructor option) and stop event plumbing with best-effort join path. | `pythonista_job_runner/app/runner_core.py`, `pythonista_job_runner/app/runner/housekeeping.py`, `pythonista_job_runner/tests/test_runner_core_runner.py` | `pytest -q pythonista_job_runner/tests/test_runner_core_runner.py -k reaper` | Needed for deterministic lifecycle/tests; default runtime behaviour preserved. |
| S01-L-01 | Low | fix_now | Clarify CPU mode contract in tests and add focused contract test for effective fallback normalization path. | `pythonista_job_runner/tests/test_runner_core.py`, `pythonista_job_runner/tests/test_runner_core_edge_cases.py`, `pythonista_job_runner/tests/test_runner_core_runner.py` | `pytest -q pythonista_job_runner/tests/test_runner_core.py -k cpu_limit_mode pythonista_job_runner/tests/test_runner_core_edge_cases.py -k cpu_limit_mode pythonista_job_runner/tests/test_runner_core_runner.py -k cpu_limit_mode` | Trivial low-risk test-contract cleanup co-located with Step 1 test updates. |
| S01-L-02 | Low | skip_with_reason | Defer broad deduplication of legacy aggregate vs split suites to avoid high-churn test reorganization during behavioural apply pass. | none | n/a | Dedup requires larger suite restructuring and is outside narrow bug-fix focus for this apply step. |

### S01 apply-only execution status
- **Findings fixed**: S01-M-01, S01-M-02, S01-L-01
- **Findings skipped**: S01-L-02 (deferred; broad suite re-organisation outside narrow Step 1 apply scope)
- **Findings invalidated**: none

Files changed in Step 1 apply:
- `pythonista_job_runner/app/runner_core.py`
- `pythonista_job_runner/app/runner/housekeeping.py` (pre-recorded narrow helper change for stop-aware reaper loop)
- `pythonista_job_runner/tests/test_runner_core_runner.py`
- `pythonista_job_runner/tests/test_runner_core.py`
- `pythonista_job_runner/tests/test_runner_core_edge_cases.py`

Validation commands run and results:
- `pytest -q pythonista_job_runner/tests/test_runner_core_runner.py -k telemetry` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_core_runner.py -k reaper` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_core.py -k cpu_limit_mode pythonista_job_runner/tests/test_runner_core_edge_cases.py -k cpu_limit_mode pythonista_job_runner/tests/test_runner_core_runner.py -k cpu_limit_mode` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_core.py` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_core_*.py` → pass
- `pytest -q` → pass
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass

## S02 — HTTP API, auth/helpers, audit, support bundle
- **Scope files**:
  - `pythonista_job_runner/app/http_api_server.py`
  - `pythonista_job_runner/app/http_api.py`
  - `pythonista_job_runner/app/http_api_auth.py`
  - `pythonista_job_runner/app/http_api_helpers.py`
  - `pythonista_job_runner/app/audit.py`
  - `pythonista_job_runner/app/support_bundle.py`
  - related tests: `pythonista_job_runner/tests/test_http_api_*.py`, `pythonista_job_runner/tests/test_support_bundle.py`, `pythonista_job_runner/tests/test_redaction.py`
- **Review output**: `reviews/S02_http_api_review.md`
- **Narrow validations**:
  - `pytest -q pythonista_job_runner/tests/test_http_api_*.py pythonista_job_runner/tests/test_support_bundle.py pythonista_job_runner/tests/test_redaction.py`

### S02 apply-only finding ledger

Helper-file scope note for Step 2 apply:
- None. Step 2 production files and their directly related tests are sufficient for safe fixes in this pass.

| Finding ID | Severity | Status | Planned action | Files expected to change | Narrow tests to run | Justification |
|---|---|---|---|---|---|---|
| S02-H-01 | High | fix_now | Ensure partial upload temp files are unlinked on `_read_body_to_tempfile` error paths, including incomplete streams. | `pythonista_job_runner/app/http_api_server.py`, `pythonista_job_runner/tests/test_http_api_basic.py` | `pytest -q pythonista_job_runner/tests/test_http_api_basic.py -k incomplete_upload` | High-severity disk/sensitive-temp retention risk; narrow and local fix. |
| S02-M-02 | Medium | fix_now | Add endpoint-level auth branch tests for ingress strict and CIDR filtering behavior. | `pythonista_job_runner/tests/test_http_api_basic.py` | `pytest -q pythonista_job_runner/tests/test_http_api_basic.py -k ingress_strict or api_allow_cidrs` | Security-sensitive policy paths need direct regression coverage. |
| S02-M-01 | Medium | fix_now | Replace full-file JSONL tail read with bounded streaming/deque tail implementation. | `pythonista_job_runner/app/support_bundle.py`, `pythonista_job_runner/tests/test_support_bundle.py` | `pytest -q pythonista_job_runner/tests/test_support_bundle.py -k tail or support_bundle` | Reliability improvement within Step 2 scope and low-risk implementation. |
| S02-L-01 | Low | fix_now | Compute support-bundle queue metrics from one `list_jobs()` snapshot for consistency. | `pythonista_job_runner/app/support_bundle.py`, `pythonista_job_runner/tests/test_support_bundle.py` | `pytest -q pythonista_job_runner/tests/test_support_bundle.py -k queue` | Trivial co-located change with M-01 in same file. |

### S02 apply-only execution status
- **Findings fixed**: S02-H-01, S02-M-02, S02-M-01, S02-L-01
- **Findings skipped**: none
- **Findings invalidated**: none

Files changed in Step 2 apply:
- `pythonista_job_runner/app/http_api_server.py`
- `pythonista_job_runner/app/support_bundle.py`
- `pythonista_job_runner/tests/test_http_api_basic.py`
- `pythonista_job_runner/tests/test_support_bundle.py`

Validation commands run and results:
- `pytest -q pythonista_job_runner/tests/test_http_api_basic.py -k incomplete_upload` → pass
- `pytest -q pythonista_job_runner/tests/test_http_api_basic.py -k 'ingress_strict or api_allow_cidrs'` → pass
- `pytest -q pythonista_job_runner/tests/test_support_bundle.py -k 'tail or support_bundle or queue'` → pass
- `pytest -q pythonista_job_runner/tests/test_http_api_*.py pythonista_job_runner/tests/test_support_bundle.py pythonista_job_runner/tests/test_redaction.py` → pass
- `pytest -q` → pass
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass

## S03 — Runner execution pipeline
- **Scope files**:
  - `pythonista_job_runner/app/runner/executor.py`
  - `pythonista_job_runner/app/runner/process.py`
  - `pythonista_job_runner/app/runner/deps.py`
  - `pythonista_job_runner/app/runner/results.py`
  - `pythonista_job_runner/app/runner/fs_safe.py`
  - `pythonista_job_runner/app/runner/hashes.py`
  - `pythonista_job_runner/app/runner/redact.py`
  - `pythonista_job_runner/app/runner/notify.py`
  - `pythonista_job_runner/app/job_runner.py`
  - related execution-path tests
- **Review output**: `reviews/S03_runner_execution_review.md`
- **Narrow validations**:
  - `pytest -q pythonista_job_runner/tests/test_runner_core_process_and_notify.py pythonista_job_runner/tests/test_runner_core_outputs_and_load.py pythonista_job_runner/tests/test_redaction.py pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py`

### S03 apply-only finding ledger

Helper-file scope note for Step 3 apply:
- None. Step 3 execution modules and directly related tests are sufficient for safe fixes in this pass.

| Finding ID | Severity | Status | Planned action | Files expected to change | Narrow tests to run | Justification |
|---|---|---|---|---|---|---|
| S03-H-01 | High | fix_now | Harden URL basic-auth redaction to avoid credential fragments leaking when password contains `@` and related edge cases. | `pythonista_job_runner/app/runner/redact.py`, `pythonista_job_runner/tests/test_redaction.py` | `pytest -q pythonista_job_runner/tests/test_redaction.py -k basic_auth` | High-severity secret-redaction correctness issue with narrow parser-based fix. |
| S03-M-01 | Medium | fix_now | Allow dependency install path in non-root mode even when job uid/gid lookup is unavailable; keep root-mode guard intact. | `pythonista_job_runner/app/runner/deps.py`, `pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py` | `pytest -q pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py -k non_root` | Medium correctness issue; local branch fix in Step 3 scope. |
| S03-M-02 | Medium | fix_now | Add TERM→wait→KILL fallback escalation when pgid lookup fails in process kill helper. | `pythonista_job_runner/app/runner/process.py`, `pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py` | `pytest -q pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py -k kill_process_group` | Medium robustness issue; small change mirrors existing main branch behavior. |
| S03-L-01 | Low | fix_now | Add targeted tests for deps branches and fs-safe helpers without broad refactor. | `pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py` | `pytest -q pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py` | Trivial co-located test expansion alongside medium fixes. |

### S03 apply-only execution status
- **Findings fixed**: S03-H-01, S03-M-01, S03-M-02, S03-L-01
- **Findings skipped**: none
- **Findings invalidated**: none

Files changed in Step 3 apply:
- `pythonista_job_runner/app/runner/redact.py`
- `pythonista_job_runner/app/runner/deps.py`
- `pythonista_job_runner/app/runner/process.py`
- `pythonista_job_runner/tests/test_redaction.py`
- `pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py`

Validation commands run and results:
- `pytest -q pythonista_job_runner/tests/test_redaction.py -k basic_auth` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py -k non_root` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py -k kill_process_group` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py` → pass
- `pytest -q pythonista_job_runner/tests/test_runner_core_process_and_notify.py pythonista_job_runner/tests/test_runner_core_outputs_and_load.py pythonista_job_runner/tests/test_redaction.py pythonista_job_runner/tests/test_runner_deps_and_fs_safe.py` → pass
- `pytest -q` → pass
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass

## S04 — Merged storage, lifecycle, persistence, housekeeping, utilities, client, and contract
- **Scope files**:
  - `pythonista_job_runner/app/runner/store.py`
  - `pythonista_job_runner/app/runner/store_index.py`
  - `pythonista_job_runner/app/runner/store_lifecycle.py`
  - `pythonista_job_runner/app/runner/store_persistence.py`
  - `pythonista_job_runner/app/runner/housekeeping.py`
  - `pythonista_job_runner/app/runner/state.py`
  - `pythonista_job_runner/app/runner/stats.py`
  - `pythonista_job_runner/app/utils.py`
  - `pythonista_job_runner/app/pythonista_client.py`
  - `pythonista_job_runner/examples/pythonista_run_job.py`
  - `pythonista_job_runner/api/openapi.json`
  - related tests: `test_job_store_registry.py`, `test_backup_pause_resume.py`, `test_api_contract.py`, `test_pythonista_client.py`, `test_utils_zip_extract.py`
- **Review output**: `reviews/S04_storage_utils_client_review.md`
- **Narrow validations**:
  - `pytest -q pythonista_job_runner/tests/test_job_store_registry.py pythonista_job_runner/tests/test_backup_pause_resume.py pythonista_job_runner/tests/test_api_contract.py pythonista_job_runner/tests/test_pythonista_client.py pythonista_job_runner/tests/test_utils_zip_extract.py`

### S04 apply-only finding ledger

Helper-file scope note for Step 4 apply:
- None. Step 4 files and directly related tests are sufficient for safe fixes in this pass.

| Finding ID | Severity | Section | Status | Planned action | Files expected to change | Narrow tests to run | Justification |
|---|---|---|---|---|---|---|---|
| S04-H-01 | High | Section A | fix_now | Use directory name (`p.name`) as authoritative housekeeping delete/discard key under low-disk cleanup fallback. | `pythonista_job_runner/app/runner/housekeeping.py`, `pythonista_job_runner/tests/test_job_store_registry.py` | `pytest -q pythonista_job_runner/tests/test_job_store_registry.py -k ensure_min_free_space_uses_directory_name` | Prevent state/disk drift when status metadata is inconsistent. |
| S04-H-02 | High | Section B | fix_now | Replace client `extractall` with guarded extraction using `safe_extract_zip_bytes` and configurable limits. | `pythonista_job_runner/app/pythonista_client.py`, `pythonista_job_runner/tests/test_pythonista_client.py` | `pytest -q pythonista_job_runner/tests/test_pythonista_client.py -k extract_result_zip_enforces` | Client-side extraction safety hardening for malicious/oversized archives. |
| S04-M-01 | Medium | Section A | fix_now | In purge path, append to deleted list only when `delete_job(...)` returns `True`. | `pythonista_job_runner/app/runner/store_lifecycle.py`, `pythonista_job_runner/tests/test_job_store_registry.py` | `pytest -q pythonista_job_runner/tests/test_job_store_registry.py -k purge_does_not_report_job_deleted` | Correct purge reporting accuracy. |
| S04-M-02 | Medium | Section B | fix_now | Extend API contract tests to assert client-required response schema refs/required fields for `/run`, `/job/{job_id}.json`, `/tail/{job_id}.json`. | `pythonista_job_runner/tests/test_api_contract.py` | `pytest -q pythonista_job_runner/tests/test_api_contract.py -k client_required_response_shapes` | Guard against contract drift that breaks client assumptions. |
| S04-L-01 | Low | Section A | fix_now | Replace source-text backup method-presence check with runtime pause/resume/status contract test. | `pythonista_job_runner/tests/test_backup_pause_resume.py` | `pytest -q pythonista_job_runner/tests/test_backup_pause_resume.py -k pause_resume_status_runtime_contract` | Low-risk co-located test quality improvement. |

### S04 apply-only execution status
- **Findings fixed**: S04-H-01, S04-H-02, S04-M-01, S04-M-02, S04-L-01
- **Findings skipped**: none
- **Findings invalidated**: none

Files changed in Step 4 apply:
- `pythonista_job_runner/app/runner/housekeeping.py`
- `pythonista_job_runner/app/runner/store_lifecycle.py`
- `pythonista_job_runner/app/pythonista_client.py`
- `pythonista_job_runner/tests/test_job_store_registry.py`
- `pythonista_job_runner/tests/test_pythonista_client.py`
- `pythonista_job_runner/tests/test_api_contract.py`
- `pythonista_job_runner/tests/test_backup_pause_resume.py`

Validation commands run and results:
- `pytest -q pythonista_job_runner/tests/test_job_store_registry.py -k ensure_min_free_space_uses_directory_name` → pass
- `pytest -q pythonista_job_runner/tests/test_pythonista_client.py -k extract_result_zip_enforces` → pass
- `pytest -q pythonista_job_runner/tests/test_job_store_registry.py -k purge_does_not_report_job_deleted` → pass
- `pytest -q pythonista_job_runner/tests/test_api_contract.py -k client_required_response_shapes` → pass
- `pytest -q pythonista_job_runner/tests/test_backup_pause_resume.py -k pause_resume_status_runtime_contract` → pass
- `pytest -q pythonista_job_runner/tests/test_job_store_registry.py pythonista_job_runner/tests/test_backup_pause_resume.py pythonista_job_runner/tests/test_api_contract.py pythonista_job_runner/tests/test_pythonista_client.py pythonista_job_runner/tests/test_utils_zip_extract.py` → pass
- `pytest -q` → pass
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass

## S05 — Merged full Web UI source system
- **Scope files**:
  - `pythonista_job_runner/app/webui_build.py`
  - `pythonista_job_runner/app/webui.py`
  - `pythonista_job_runner/app/webui_src.html`
  - `pythonista_job_runner/app/webui_js/*.js`
  - `pythonista_job_runner/app/webui_html/*.html`
  - `pythonista_job_runner/app/webui_css/*.css`
  - related Web UI generation, JS, DOM, layout, and accessibility tests
- **Review output**: `reviews/S05_webui_full_review.md`
- **Narrow validations**:
  - `cd pythonista_job_runner && python app/webui_build.py --check`
  - `pytest -q pythonista_job_runner/tests/test_webui*.py`
  - `cd pythonista_job_runner && node --check app/webui.js`

### S05 apply-only finding ledger

Helper-file scope note for Step 5 apply:
- None. Step 5 Web UI source/generator files and directly related tests are sufficient for safe fixes in this pass.

| Finding ID | Severity | Section | Status | Planned action | Files expected to change | Narrow tests to run | Justification |
|---|---|---|---|---|---|---|---|
| S05-M-01 | Medium | Section A | fix_now | Expand root-relative guardrail pattern coverage and add focused build guardrail tests for newly-covered forms. | `pythonista_job_runner/app/webui_build.py`, `pythonista_job_runner/tests/test_webui_root_relative_guardrail.py` | `pytest -q pythonista_job_runner/tests/test_webui_root_relative_guardrail.py -k root_relative_new_url` | Medium guardrail gap; narrow source+test fix in generator scope. |
| S05-L-01 | Low | Section A | fix_now | Cache template text in `webui.py` to avoid per-request disk reads while preserving version substitution behavior. | `pythonista_job_runner/app/webui.py`, `pythonista_job_runner/tests/test_webui_py.py` | `pytest -q pythonista_job_runner/tests/test_webui_py.py` | Trivial co-located performance improvement. |
| S05-M-02 | Medium | Section B | fix_now | Introduce safe localStorage wrappers and migrate JS storage reads/writes/removes to wrapper calls. | `pythonista_job_runner/app/webui_js/00_core.js`, `pythonista_job_runner/app/webui_js/40_events_init.js`, `pythonista_job_runner/tests/test_webui_js_regressions.py` | `pytest -q pythonista_job_runner/tests/test_webui_js_regressions.py -k localstorage_access_uses_safe_wrappers` | Medium resilience issue; wrapper approach keeps behavior while preventing init breakage. |
| S05-L-02 | Low | Section B | skip_with_reason | Defer broad regression-suite redesign from string-pattern checks to runtime behavior harness due wider test-architecture churn beyond narrow Step 5 apply. | none | n/a | Requires larger harness changes not necessary for current bug-fix set. |
| S05-L-03 | Low | Section C | fix_now | Ban per-part HTML Version comments in builder and remove stale comments from HTML partials. | `pythonista_job_runner/app/webui_build.py`, `pythonista_job_runner/app/webui_html/*.html`, `pythonista_job_runner/tests/test_webui_root_relative_guardrail.py` | `pytest -q pythonista_job_runner/tests/test_webui_root_relative_guardrail.py -k version_header_comment_in_html_parts` | Low-risk consistency cleanup co-located with build guardrails. |

### S05 apply-only execution status
- **Findings fixed**: S05-M-01, S05-L-01, S05-M-02, S05-L-03
- **Findings skipped**: S05-L-02 (broad regression-suite redesign deferred due out-of-scope harness churn)
- **Findings invalidated**: none

Files changed in Step 5 apply:
- `pythonista_job_runner/app/webui_build.py`
- `pythonista_job_runner/app/webui.py`
- `pythonista_job_runner/app/webui_js/00_core.js`
- `pythonista_job_runner/app/webui_js/40_events_init.js`
- `pythonista_job_runner/app/webui_html/*.html`
- `pythonista_job_runner/app/webui.js` (derived, regenerated)
- `pythonista_job_runner/app/webui.html` (derived, regenerated)
- `pythonista_job_runner/tests/test_webui_root_relative_guardrail.py`
- `pythonista_job_runner/tests/test_webui_js_regressions.py`
- `pythonista_job_runner/tests/test_webui_py.py`

Validation commands run and results:
- `pytest -q pythonista_job_runner/tests/test_webui_root_relative_guardrail.py -k root_relative_new_url` → pass
- `pytest -q pythonista_job_runner/tests/test_webui_py.py` → pass
- `pytest -q pythonista_job_runner/tests/test_webui_js_regressions.py -k localstorage_access_uses_safe_wrappers` → pass
- `pytest -q pythonista_job_runner/tests/test_webui_root_relative_guardrail.py -k version_header_comment_in_html_parts` → pass
- `cd pythonista_job_runner && python app/webui_build.py` → pass
- `pytest -q pythonista_job_runner/tests/test_webui*.py` → pass
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass
- `pytest -q` → pass

## S06 — Merged full custom integration
- **Scope files**:
  - `custom_components/pythonista_job_runner/__init__.py`
  - `custom_components/pythonista_job_runner/client.py`
  - `custom_components/pythonista_job_runner/coordinator.py`
  - `custom_components/pythonista_job_runner/const.py`
  - `custom_components/pythonista_job_runner/sensor.py`
  - `custom_components/pythonista_job_runner/diagnostics.py`
  - `custom_components/pythonista_job_runner/system_health.py`
  - `custom_components/pythonista_job_runner/repairs.py`
  - `custom_components/pythonista_job_runner/release.py`
  - `custom_components/pythonista_job_runner/config_flow.py`
  - `custom_components/pythonista_job_runner/services.py`
  - `custom_components/pythonista_job_runner/runtime_entities.py`
  - `custom_components/pythonista_job_runner/number.py`
  - `custom_components/pythonista_job_runner/select.py`
  - `custom_components/pythonista_job_runner/text.py`
  - `custom_components/pythonista_job_runner/button.py`
  - `custom_components/pythonista_job_runner/event.py`
  - `custom_components/pythonista_job_runner/update.py`
  - `custom_components/pythonista_job_runner/notify.py`
  - `custom_components/pythonista_job_runner/notifications.py`
  - `custom_components/pythonista_job_runner/intents.py`
  - translations and sentence files directly related to this slice
  - related custom integration tests
- **Review output**: `reviews/S06_custom_integration_full_review.md`
- **Narrow validations**:
  - `pytest -q tests/test_custom_integration*.py`

## S06 apply-only finding ledger

Helper-file scope note for Step 6 apply:
- None. Step 6 integration files and direct integration tests are sufficient for safe fixes in this pass.

| Finding ID | Severity | Section | Status | Planned action | Files expected to change | Narrow tests to run | Justification |
|---|---|---|---|---|---|---|---|
| S06-H-01 | High | Section A | fix_now | Honor `verify_ssl` by passing explicit SSL context to `urlopen` in client GET/POST paths. | `custom_components/pythonista_job_runner/client.py`, `tests/test_custom_integration_runtime_guards.py` | `pytest -q tests/test_custom_integration_runtime_guards.py -k verify_ssl` | High-severity correctness/security mismatch between option and transport behavior. |
| S06-M-01 | Medium | Section A | fix_now | Store backup event unsubs on setup and call them during unload to prevent duplicate listeners across reloads. | `custom_components/pythonista_job_runner/__init__.py`, `tests/test_custom_integration_runtime_guards.py` | `pytest -q tests/test_custom_integration_runtime_guards.py -k backup_listener` | Medium lifecycle reliability issue in integration setup/unload path. |
| S06-M-02 | Medium | Section B | fix_now | Register each service independently instead of returning early if one service already exists. | `custom_components/pythonista_job_runner/services.py`, `tests/test_custom_integration_runtime_guards.py` | `pytest -q tests/test_custom_integration_runtime_guards.py -k service_registration` | Medium control-surface robustness issue in partial-registration scenarios. |

### S06 apply-only execution status
- **Findings fixed**: S06-H-01, S06-M-01, S06-M-02
- **Findings skipped**: none
- **Findings invalidated**: none

Files changed in Step 6 apply:
- `reviews/S06_custom_integration_full_review.md`
- `custom_components/pythonista_job_runner/client.py`
- `custom_components/pythonista_job_runner/__init__.py`
- `custom_components/pythonista_job_runner/services.py`
- `tests/test_custom_integration_runtime_guards.py`

Validation commands run and results:
- `pytest -q tests/test_custom_integration_runtime_guards.py -k verify_ssl` → pass
- `pytest -q tests/test_custom_integration_runtime_guards.py -k backup_listener` → pass
- `pytest -q tests/test_custom_integration_runtime_guards.py -k service_registration` → pass
- `pytest -q tests/test_custom_integration*.py` → pass
- `pytest -q` → pass
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass

## S07 — Add-on packaging, security, and repository automation
- **Scope files**:
  - `pythonista_job_runner/Dockerfile`
  - `pythonista_job_runner/apparmor.txt`
  - `pythonista_job_runner/config.yaml`
  - `pythonista_job_runner/build.yaml`
  - `repository.yaml`
  - workflow/metadata/security files under repo root
  - packaging and guardrail tests
- **Review output**: `reviews/S07_packaging_security_review.md`
- **Narrow validations**:
  - `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py pythonista_job_runner/tests/test_docs_links_exist.py pythonista_job_runner/tests/test_readme_screenshot_assets.py pythonista_job_runner/tests/test_screenshot_filename_contract.py`

## S07 apply-only finding ledger

Helper-file scope note for Step 7 apply:
- None. Step 7 packaging/workflow files and direct packaging guardrail tests are sufficient for safe fixes in this pass.

| Finding ID | Severity | Status | Planned action | Files expected to change | Narrow tests to run | Justification |
|---|---|---|---|---|---|---|
| S07-H-01 | High | fix_now | Remove add-on user configurability for `runner.bind_port` and add guardrail asserting fixed 8787 contract across config metadata and Docker healthcheck. | `pythonista_job_runner/config.yaml`, `pythonista_job_runner/tests/test_addon_packaging_guardrails.py` | `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py -k bind_port_contract` | High packaging/runtime contract mismatch with direct service availability impact. |
| S07-M-01 | Medium | fix_now | Replace exact Alpine package revision pins with unpinned package names and add guardrail test enforcing non-revision-pinned policy. | `pythonista_job_runner/Dockerfile`, `pythonista_job_runner/tests/test_addon_packaging_guardrails.py` | `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py -k dockerfile_apk_policy` | Medium build fragility; narrow and safe Dockerfile policy fix. |
| S07-M-02 | Medium | fix_now | Update CI pytest job to run from repository root and add workflow guardrail test for root-level `pytest -q`. | `.github/workflows/lint.yml`, `pythonista_job_runner/tests/test_addon_packaging_guardrails.py` | `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py -k workflow_runs_root_pytest` | Medium CI coverage blind spot; scoped workflow-only change. |
| S07-L-01 | Low | skip_with_reason | Defer YAML AST parser migration in packaging guardrail tests to avoid introducing/maintaining additional YAML test dependency in CI job for this narrow apply pass. | none | n/a | Low-severity quality improvement, not required to safely fix High/Medium findings this step. |

### S07 apply-only execution status
- **Findings fixed**: S07-H-01, S07-M-01, S07-M-02
- **Findings skipped**: S07-L-01 (YAML AST parser migration deferred as low-severity dependency/harness change outside this narrow apply pass)
- **Findings invalidated**: none

Files changed in Step 7 apply:
- `reviews/FULL_CODE_REVIEW_PLAN.md`
- `pythonista_job_runner/config.yaml`
- `pythonista_job_runner/Dockerfile`
- `.github/workflows/lint.yml`
- `pythonista_job_runner/tests/test_addon_packaging_guardrails.py`

Validation commands run and results:
- `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py -k bind_port_contract` → pass
- `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py -k dockerfile_apk_policy` → pass
- `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py -k workflow_runs_root_pytest` → pass
- `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py pythonista_job_runner/tests/test_docs_links_exist.py pythonista_job_runner/tests/test_readme_screenshot_assets.py pythonista_job_runner/tests/test_screenshot_filename_contract.py` → pass
- `pytest -q` → pass
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass

## Repo-wide validation commands (post-apply or milestone checks)
- `pytest -q`
- `cd pythonista_job_runner && python app/webui_build.py --check`
- `cd pythonista_job_runner && node --check app/webui.js`
