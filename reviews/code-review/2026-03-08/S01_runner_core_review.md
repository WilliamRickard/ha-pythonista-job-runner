Version: 0.6.12-review-s01.1
# S01 Runner Core Review (Review-only pass)

## Executive summary

This Step 1 review focused on `runner_core.py` and its directly related runner-core tests. The slice is in generally good shape and baseline + narrow tests pass, but there are meaningful reliability and test-contract issues that should be addressed before deeper refactors. No Critical or High defects were confirmed in this pass; two Medium and two Low findings were identified.

## Files reviewed

### Production
- `pythonista_job_runner/app/runner_core.py`

### Directly related runner-core tests
- `pythonista_job_runner/tests/test_runner_core.py`
- `pythonista_job_runner/tests/test_runner_core_job.py`
- `pythonista_job_runner/tests/test_runner_core_runner.py`
- `pythonista_job_runner/tests/test_runner_core_options_and_helpers.py`
- `pythonista_job_runner/tests/test_runner_core_outputs_and_load.py`
- `pythonista_job_runner/tests/test_runner_core_process_and_notify.py`
- `pythonista_job_runner/tests/test_runner_core_edge_cases.py`
- `pythonista_job_runner/tests/test_runner_core_regressions_apply.py`

### Nearby helper inspected for reasoning support
- `pythonista_job_runner/app/runner/store_lifecycle.py` (only CPU-limit parsing path used to validate a runner-core test contract concern)

## Baseline validation context

The baseline commands were already executed in the initial programme pass and are still the authoritative baseline for Step 1:
- `pytest -q` → pass (`221 passed`)
- `cd pythonista_job_runner && python app/webui_build.py --check` → pass
- `cd pythonista_job_runner && node --check app/webui.js` → pass

Additional narrow validation executed for this review run:
- `pytest -q pythonista_job_runner/tests/test_runner_core*.py` → pass (`97 passed`)

No blocking edits were required for validation.

## Positive observations

- `Runner` option parsing consistently clamps numeric limits through a single local helper, reducing scattered range-check logic and preventing many invalid-config failure modes.
- Audit event persistence and telemetry publication are decoupled so telemetry network failures do not block core audit logging paths.
- The runner-core test suite includes meaningful regression coverage (queue limit race, large stdout no-newline, missing `job_user` under root simulation), which is valuable for future apply work.
- The module has clean delegation boundaries to `runner/*` helpers (`store`, `executor`, `results`, `housekeeping`, etc.), making targeted remediation possible without broad rewrites.

## Findings by severity

## Critical

### No findings
No direct data-loss, corruption, or security-break issue was confirmed in this Step 1 scope.

## High

### No findings
No high-probability serious runtime failure was confirmed in reviewed runner-core behaviours.

## Medium

### S01-M-01
- **Severity:** Medium
- **Title:** Telemetry publication creates unbounded daemon threads under event load
- **File and region:** `pythonista_job_runner/app/runner_core.py`, `Runner.publish_telemetry` (`threading.Thread(...).start()` per event).
- **Description of the issue:** Every telemetry call spawns a brand-new daemon thread with no concurrency cap, queue, or worker reuse.
- **Why it matters:** In bursty audit/event scenarios, thread count can grow quickly and unpredictably, increasing context-switch overhead and memory pressure; this can degrade runner responsiveness even when telemetry is optional.
- **Evidence / reasoning:** `publish_telemetry` builds a worker closure and unconditionally starts a new thread for each event when telemetry is enabled. No rate limit, bounded queue, or pool is present. Runner-core tests do not currently exercise this behaviour (`rg -n "publish_telemetry|telemetry_mqtt_enabled" pythonista_job_runner/tests/test_runner_core*.py` returned no matches).
- **Recommended narrow fix:** Replace per-event thread creation with a bounded background worker model (single worker + queue, or small fixed pool) and drop/merge policy when the queue is full.
- **Tests to add/update:** Add runner-core tests that emit many telemetry events with telemetry enabled and assert bounded worker behaviour (e.g., queue limit respected, core call path remains non-blocking, no unbounded thread growth).

### S01-M-02
- **Severity:** Medium
- **Title:** Runner constructor always starts a reaper thread without lifecycle control
- **File and region:** `pythonista_job_runner/app/runner_core.py`, `Runner.__init__` background startup (`self._load_jobs_from_disk(); threading.Thread(target=self._reaper, daemon=True).start()`).
- **Description of the issue:** Creating a `Runner` instance always starts a daemon reaper thread, with no explicit stop signal, join path, or constructor option to suppress background startup in controlled contexts.
- **Why it matters:** This weakens test/process determinism and complicates embedding/reuse scenarios where caller-managed lifecycle is expected.
- **Evidence / reasoning:** The constructor unconditionally starts the thread after job loading. No visible stop API exists in runner_core for this thread lifecycle.
- **Recommended narrow fix:** Add optional lifecycle controls (e.g., `start_reaper: bool = True`) and a stop event plumbed into reaper loop handling; keep default behaviour unchanged for add-on runtime.
- **Tests to add/update:** Add a runner-core test asserting `Runner(start_reaper=False)` performs initialization without starting background reaper activity; add a stop/cleanup lifecycle test if stop support is added.

## Low

### S01-L-01
- **Severity:** Low
- **Title:** CPU mode test contract is misleading and conflicts with actual effective-mode behaviour
- **File and region:**
  - `pythonista_job_runner/tests/test_runner_core.py` (`test_runner_cpu_limit_mode_validation`)
  - `pythonista_job_runner/tests/test_runner_core_edge_cases.py` (`test_cpu_limit_mode_is_stored_as_given`)
  - reasoning support: `pythonista_job_runner/app/runner/store_lifecycle.py` (`_parse_limits` mode normalization)
- **Description of the issue:** Test names/comments claim CPU mode validation or fallback semantics, but assertions intentionally expect raw invalid mode storage (`"invalid_mode"`).
- **Why it matters:** This creates a confusing contract boundary: reader expectation is that `Runner` validates mode immediately, while actual behaviour normalizes later in store-lifecycle parsing.
- **Evidence / reasoning:** In `test_runner_core.py`, the test docstring says validation/fallback, but the assertion checks stored invalid mode. In nearby runtime logic, `_parse_limits` falls back invalid modes to `single_core` for effective limits.
- **Recommended narrow fix:** Clarify and align test intent explicitly: either (a) rename tests/comments to state "runner stores raw config; normalization happens at limit parse time", or (b) move validation to runner construction and update tests accordingly.
- **Tests to add/update:** Add a focused contract test asserting end-to-end effective CPU mode for invalid configured value (through job-limit parsing path), so the intended normalization boundary is explicit.

### S01-L-02
- **Severity:** Low
- **Title:** Runner-core test coverage is duplicated across legacy aggregate and split test modules
- **File and region:** `pythonista_job_runner/tests/test_runner_core.py` and overlapping scenarios in `test_runner_core_job.py`, `test_runner_core_runner.py`, `test_runner_core_options_and_helpers.py`, `test_runner_core_process_and_notify.py`, `test_runner_core_edge_cases.py`.
- **Description of the issue:** Many behaviours are asserted in multiple files with near-identical expectations.
- **Why it matters:** Duplicated tests increase maintenance cost and can create drift/conflicting expectations over time.
- **Evidence / reasoning:** Overlap exists for job defaults/status, read-options behaviour, user-id resolution, process-kill helper behaviour, runner initialization defaults, queue-full behaviour, and env filtering.
- **Recommended narrow fix:** Keep one canonical suite organization (prefer split module-oriented suites) and remove or trim duplicate legacy cases while preserving unique regression checks.
- **Tests to add/update:** When deduplicating, ensure coverage parity via parametrized cases and retain unique regression tests (`test_runner_core_regressions_apply.py`).

## Apply guidance

Recommended apply order for S01 follow-up:
1. **S01-M-01 first**: introduce bounded telemetry worker model + tests (contains potential performance-risk surface).
2. **S01-M-02 second**: introduce explicit runner reaper lifecycle control + deterministic tests.
3. **S01-L-01 third**: resolve CPU mode contract clarity (code-path or test-contract alignment, pick one and document).
4. **S01-L-02 last**: deduplicate tests after behavioural contracts are finalized, to avoid churn.

Keep apply work strictly inside Step 1 scope (`runner_core.py` and directly related tests/helpers needed for those findings).
