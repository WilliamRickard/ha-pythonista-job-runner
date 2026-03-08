Version: 0.6.12-review-s02.1
# S02 HTTP API Review (Review-only pass)

## Executive summary

This Step 2 review covered the HTTP API/auth/helpers, audit logging, and support-bundle surfaces plus their directly related tests. The slice is generally structured well and targeted tests pass, but there are meaningful issues around upload-tempfile cleanup, support-bundle tailing scalability, and auth-surface test coverage. No Critical findings were confirmed in this pass.

## Files reviewed

### Production
- `pythonista_job_runner/app/http_api_server.py`
- `pythonista_job_runner/app/http_api.py`
- `pythonista_job_runner/app/http_api_auth.py`
- `pythonista_job_runner/app/http_api_helpers.py`
- `pythonista_job_runner/app/audit.py`
- `pythonista_job_runner/app/support_bundle.py`

### Directly related tests
- `pythonista_job_runner/tests/test_http_api_basic.py`
- `pythonista_job_runner/tests/test_http_api_lifecycle_integration.py`
- `pythonista_job_runner/tests/test_support_bundle.py`
- `pythonista_job_runner/tests/test_redaction.py`

### Nearby helper inspected for reasoning support
- `pythonista_job_runner/tests/conftest.py` (fixture behavior for HTTP API tests)

## Validation context

Baseline validations are already recorded in `reviews/FULL_CODE_REVIEW_PLAN.md` and were not re-run broadly in this slice.

Commands executed for this Step 2 review:
- `pytest -q pythonista_job_runner/tests/test_http_api_*.py pythonista_job_runner/tests/test_support_bundle.py pythonista_job_runner/tests/test_redaction.py` (pass: 25 passed)
- `python -m py_compile pythonista_job_runner/app/http_api_server.py pythonista_job_runner/app/http_api.py pythonista_job_runner/app/http_api_auth.py pythonista_job_runner/app/http_api_helpers.py pythonista_job_runner/app/audit.py pythonista_job_runner/app/support_bundle.py` (pass)
- `rg -n "auth_ok|is_ingress|client_ip|actor_from_headers|append_audit_event|support_bundle|/support_bundle|/purge|/run|ingress_strict|api_allow_cidrs" pythonista_job_runner/tests/test_http_api_basic.py pythonista_job_runner/tests/test_http_api_lifecycle_integration.py pythonista_job_runner/tests/test_support_bundle.py` (inspection)

No production edits were made.

## Positive observations

- HTTP request handlers centralize common response primitives (`_json`, `_send_bytes`, `_validate_content_type`) which keeps response-shape behavior consistent.
- RuntimeError text from job submission is sanitized via `safe_runtime_error_code`, reducing risk of arbitrary internal error text leaking through API responses.
- The integration tests exercise realistic endpoint lifecycle churn (`/run`, `/cancel`, `/tail`, `/stdout`, `/result`, `/job`) and concurrent read pressure, which is strong coverage for API wiring behavior.
- Audit actor extraction gates ingress identity headers by source IP match, preventing blind trust of ingress headers from arbitrary remote clients.

## Findings by severity

## Critical

### No findings
No direct auth bypass, secret-leak, or destructive runtime break was conclusively demonstrated in-scope for this pass.

## High

### S02-H-01
- **Severity:** High
- **Title:** Incomplete uploads can leave undeleted partial zip temp files in `/tmp`
- **File and region:** `pythonista_job_runner/app/http_api_server.py`, `_read_body_to_tempfile` and `_handle_run_post` cleanup path.
- **Description of the issue:** When request body streaming ends early (`incomplete_upload`), `_read_body_to_tempfile` returns `(error, None, None)` after creating/writing a temp file, and `_handle_run_post` cannot unlink it because it only unlinks when a non-`None` `upload_path` is returned.
- **Why it matters:** Repeated incomplete uploads can accumulate partial payload files in `/tmp` (disk pressure + retention of potentially sensitive uploaded content).
- **Evidence / reasoning:** `_read_body_to_tempfile` creates a temp file via `mkstemp` and returns `"incomplete_upload", None, None` on short read. `_handle_run_post` only unlinks `upload_path` in its `finally` block; when `upload_path is None`, no cleanup occurs.
- **Recommended narrow fix:** Ensure `_read_body_to_tempfile` always unlinks on error paths before returning, or return the created path even on error and let caller cleanup uniformly.
- **Tests to add/update:** Add an HTTP API test that sends a truncated body (declared length > bytes sent) and asserts no new `upload_*.zip` file remains in `/tmp` after response.

## Medium

### S02-M-01
- **Severity:** Medium
- **Title:** Support-bundle audit tail implementation reads full audit file into memory
- **File and region:** `pythonista_job_runner/app/support_bundle.py`, `_tail_jsonl`.
- **Description of the issue:** `_tail_jsonl` uses `read_text(...).splitlines()` and then slices the last N lines. This loads the entire audit log into memory even though only tail entries are needed.
- **Why it matters:** Large audit logs can cause avoidable memory spikes and latency on `/support_bundle.json`, reducing reliability during troubleshooting (when logs may already be large).
- **Evidence / reasoning:** `_tail_jsonl` reads whole file content first, then iterates `lines[-max_lines:]`.
- **Recommended narrow fix:** Implement bounded tail reading (seek from end in chunks, or line-iterator with bounded deque) so memory scales with `max_lines`, not file size.
- **Tests to add/update:** Add a test with a large synthetic audit log (many lines) and assert tail correctness while verifying implementation avoids full-file loading pattern (e.g., by monkeypatching read path / using chunked helper).

### S02-M-02
- **Severity:** Medium
- **Title:** Auth policy branches (ingress strict + CIDR filtering) lack direct endpoint-level tests
- **File and region:**
  - `pythonista_job_runner/app/http_api_auth.py` (`auth_ok` branch logic)
  - endpoint gate usage in `pythonista_job_runner/app/http_api_server.py` (`_require_auth` call sites)
  - related tests in `pythonista_job_runner/tests/test_http_api_basic.py` and `test_http_api_lifecycle_integration.py`
- **Description of the issue:** Existing tests validate token-required behavior and public endpoints, but do not directly verify key auth branches: ingress-strict rejection for non-ingress, ingress allowance behavior, and `api_allow_cidrs` filtering interaction with valid token.
- **Why it matters:** This is a security-sensitive policy surface. Missing direct tests increase regression risk for auth confusion or accidental branch inversion.
- **Evidence / reasoning:** Targeted grep over HTTP API/support tests found no assertions around `ingress_strict`/`api_allow_cidrs` behavior or direct `auth_ok` branch coverage.
- **Recommended narrow fix:** Add focused tests that exercise each auth policy branch with explicit handler client IP and config combinations.
- **Tests to add/update:**
  - token valid but client IP outside allowed CIDRs → 401
  - token valid and in allowed CIDRs → 200
  - ingress strict enabled, non-ingress IP with valid token → 401
  - ingress source IP path accepted without token (explicit expected behavior)

## Low

### S02-L-01
- **Severity:** Low
- **Title:** Queue summary in support bundle uses repeated unsnapshotted `list_jobs()` calls
- **File and region:** `pythonista_job_runner/app/support_bundle.py`, `build_support_bundle` queue section.
- **Description of the issue:** `build_support_bundle` calls `runner.list_jobs()` multiple times while building queue counts (`jobs_total`, `jobs_running`, `jobs_queued`, `jobs_error`).
- **Why it matters:** Under concurrent mutations this can produce internally inconsistent summary values (e.g., totals/counts from different snapshots), which can confuse diagnostics.
- **Evidence / reasoning:** queue fields each call `runner.list_jobs()` independently instead of deriving from one local snapshot list.
- **Recommended narrow fix:** Capture one local `jobs_snapshot = runner.list_jobs()` and compute all queue metrics from that snapshot.
- **Tests to add/update:** Add a deterministic support-bundle test asserting queue math consistency from a seeded job set; if feasible, add a concurrency-stress check for stable shape.

## Apply guidance

Recommended fix order for later S02 apply-only pass:
1. **S02-H-01 first** (temp-file leak risk on malformed uploads).
2. **S02-M-02 second** (auth-surface branch coverage to lock policy behavior before refactors).
3. **S02-M-01 third** (support-bundle tail scalability improvement).
4. **S02-L-01 last** (snapshot consistency/cleanup refinement in support-bundle queue assembly).

Keep apply work tightly scoped to Step 2 modules and directly related tests.
