Version: 0.6.12-review-s03.1
# S03 Runner Execution Pipeline Review (Review-only pass)

## Executive summary

This Step 3 review covered the runner execution pipeline modules (executor/process/deps/results/fs safety/redaction/notify/hashes/entrypoint) and directly related execution-path tests. The slice has solid modular decomposition and core lifecycle coverage, but there are meaningful issues around redaction correctness, dependency-install behavior under non-root fallback, and process-termination robustness. No Critical findings were confirmed in this pass.

## Files reviewed

### Production
- `pythonista_job_runner/app/runner/executor.py`
- `pythonista_job_runner/app/runner/process.py`
- `pythonista_job_runner/app/runner/deps.py`
- `pythonista_job_runner/app/runner/results.py`
- `pythonista_job_runner/app/runner/fs_safe.py`
- `pythonista_job_runner/app/runner/redact.py`
- `pythonista_job_runner/app/runner/notify.py`
- `pythonista_job_runner/app/runner/hashes.py`
- `pythonista_job_runner/app/job_runner.py`

### Directly related execution-path tests
- `pythonista_job_runner/tests/test_runner_core_process_and_notify.py`
- `pythonista_job_runner/tests/test_runner_core_outputs_and_load.py`
- `pythonista_job_runner/tests/test_runner_core_regressions_apply.py`
- `pythonista_job_runner/tests/test_redaction.py`
- `pythonista_job_runner/tests/test_job_runner.py`
- `pythonista_job_runner/tests/test_smoke_compile.py`

### Small nearby helper examined for context
- `pythonista_job_runner/app/runner_core.py` (job-user fallback semantics referenced by deps finding)

## Validation context

Baseline validations are already recorded in `reviews/FULL_CODE_REVIEW_PLAN.md`; they were not repeated broadly.

Commands executed for this Step 3 review:
- `pytest -q pythonista_job_runner/tests/test_runner_core_process_and_notify.py pythonista_job_runner/tests/test_runner_core_outputs_and_load.py pythonista_job_runner/tests/test_redaction.py pythonista_job_runner/tests/test_job_runner.py pythonista_job_runner/tests/test_runner_core_regressions_apply.py` (pass: 14 passed)
- `python -m py_compile pythonista_job_runner/app/runner/executor.py pythonista_job_runner/app/runner/process.py pythonista_job_runner/app/runner/deps.py pythonista_job_runner/app/runner/results.py pythonista_job_runner/app/runner/fs_safe.py pythonista_job_runner/app/runner/redact.py pythonista_job_runner/app/runner/notify.py pythonista_job_runner/app/runner/hashes.py pythonista_job_runner/app/job_runner.py` (pass)
- `python - <<'PY' ...` redaction spot-check for URL passwords containing `@` (inspection command; demonstrated partial secret leakage in output)
- `rg -n "install_requirements|pip_timeout|pip_index_url|pip_extra_index_url|pip_trusted_hosts|safe_write_text_no_symlink|safe_zip_write|kill_process_group\(|notify_done\(|notification_excerpt|manifest_sha256|outputs_max_bytes" pythonista_job_runner/tests` (inspection; confirms coverage gaps for several execution-path branches)

No production edits were made.

## Positive observations

- `executor.run_job` cleanly separates major lifecycle phases (queued/running/complete/error), including result packaging and notification hooks.
- Output packaging in `results.make_result_zip` is deterministic (`os.walk` sorting) and supports explicit file/byte truncation limits with a manifest reason.
- Helper boundaries (`process`, `deps`, `redact`, `fs_safe`, `notify`) reduce coupling and support targeted apply-pass changes.
- Existing regressions cover an important non-newline stdout pump case that can otherwise deadlock line-oriented readers.

## Findings by severity

## Critical

### No findings
No direct destructive execution-safety or data-loss break was conclusively demonstrated in-scope.

## High

### S03-H-01
- **Severity:** High
- **Title:** Basic-auth URL redaction leaks secrets when password contains `@`
- **File and region:** `pythonista_job_runner/app/runner/redact.py`, `redact_basic_auth_in_urls` regex replacement path.
- **Description of the issue:** The regex redaction logic assumes password text does not contain `@`. When `@` appears in password content, redaction truncates early and can leak password fragments into output.
- **Why it matters:** This affects secret-safety paths used by pip/install error and notification excerpts (`redact_pip_text` + `notify_done`), creating a real credential-leak risk in logs/notifications.
- **Evidence / reasoning:** Manual check showed `https://alice:p@ss@example.com/simple` becoming `https://alice:***@ss@example.com/simple` (the `ss` password fragment leaks). Current tests only cover simple credentials without `@` in password.
- **Recommended narrow fix:** Replace regex-only redaction with URL parsing that robustly handles encoded/unencoded credentials (or stricter pattern that masks from scheme to last `@` before host) and preserves host integrity.
- **Tests to add/update:** Extend redaction tests with cases containing `@`, `:`, and percent-encoded credentials in password values, and verify zero credential fragments remain.

## Medium

### S03-M-01
- **Severity:** Medium
- **Title:** Dependency install path is disabled when job user lookup fails even in non-root mode
- **File and region:** `pythonista_job_runner/app/runner/deps.py`, `maybe_install_requirements` early `job_uid/job_gid` gate.
- **Description of the issue:** `maybe_install_requirements` returns `pip_install_disabled_no_job_user` whenever `_job_uid/_job_gid` are missing, regardless of whether runner is actually root.
- **Why it matters:** In non-root environments where username lookup is unavailable (or intentionally absent), jobs can still run as current user, but dependency installation is forcibly disabled and job fails when `install_requirements` is enabled.
- **Evidence / reasoning:** `deps.py` gates on missing uid/gid before checking root context. In runner initialization, missing job user under non-root is explicitly treated as “jobs will run as current user,” indicating fallback intent.
- **Recommended narrow fix:** Require uid/gid only when `_is_root` is true; in non-root mode allow pip install to proceed without privilege dropping.
- **Tests to add/update:** Add a test simulating non-root + missing uid/gid + `install_requirements=True` to verify the path does not fail with `pip_install_disabled_no_job_user`.

### S03-M-02
- **Severity:** Medium
- **Title:** Process-group fallback path may leave stubborn child process alive
- **File and region:** `pythonista_job_runner/app/runner/process.py`, `kill_process_group` exception path when `os.getpgid` fails.
- **Description of the issue:** If process-group lookup fails, implementation sends only `p.terminate()` and returns immediately without wait/escalation.
- **Why it matters:** Processes that ignore or delay SIGTERM can survive cancellation/timeout paths, leaving straggler subprocesses consuming resources.
- **Evidence / reasoning:** Fallback branch returns right after `terminate()`. Main branch has TERM→wait→KILL escalation, but fallback does not.
- **Recommended narrow fix:** In fallback branch, mirror staged termination: `terminate()`, short wait/poll loop, then `kill()` if still alive.
- **Tests to add/update:** Add unit test using a mock process where `getpgid` fails and `poll()` remains `None` after `terminate()`, asserting escalation to `kill()` occurs.

## Low

### S03-L-01
- **Severity:** Low
- **Title:** Execution pipeline modules have limited direct test coverage for dependency/install and fs-safety helpers
- **File and region:**
  - `pythonista_job_runner/app/runner/deps.py`
  - `pythonista_job_runner/app/runner/fs_safe.py`
  - coverage observation across `pythonista_job_runner/tests/test_runner_core_process_and_notify.py`, `test_runner_core_outputs_and_load.py`, `test_redaction.py`, `test_runner_core_regressions_apply.py`
- **Description of the issue:** Existing tests strongly cover process kill, output manifests, and basic redaction, but there are no focused tests for many `deps.py` branches (timeout/nonzero rc/redaction persistence), and no direct tests for fs-safety helper semantics.
- **Why it matters:** These are safety-relevant branches where regressions can surface as secret leaks, brittle cleanup, or unsafe file handling without quick detection.
- **Evidence / reasoning:** Targeted grep over tests found no direct assertions on most pip/deps/fs-safe helper paths.
- **Recommended narrow fix:** Add compact module-level tests for `maybe_install_requirements` branch outcomes and `safe_write_text_no_symlink` / `safe_zip_write` guardrails.
- **Tests to add/update:**
  - deps: success, timeout, rc!=0, and exception/redaction cases
  - fs_safe: symlink refusal and base-dir containment behavior in zip writes

## Apply guidance

Recommended implementation order for S03 apply-only pass:
1. **S03-H-01 first** (credential redaction correctness / leak prevention).
2. **S03-M-01 second** (non-root dependency-install correctness).
3. **S03-M-02 third** (process-termination robustness and orphan prevention).
4. **S03-L-01 last** (targeted test expansion once behavior decisions are fixed).

Keep apply work restricted to S03 modules and directly related tests.
