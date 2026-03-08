# S07 Packaging, Security, and Repository Automation Review (Step 7, review-only)

## Scope
Review-only assessment for add-on packaging, security posture, and repository automation.

In-scope production/configuration files:
- `pythonista_job_runner/config.yaml`
- `pythonista_job_runner/build.yaml`
- `pythonista_job_runner/apparmor.txt`
- `pythonista_job_runner/Dockerfile`
- `pythonista_job_runner/run.sh`
- `repository.yaml`
- `.github/workflows/lint.yml`

In-scope tests/guardrails reviewed:
- `pythonista_job_runner/tests/test_addon_packaging_guardrails.py`
- `pythonista_job_runner/tests/test_docs_links_exist.py`
- `pythonista_job_runner/tests/test_readme_screenshot_assets.py`
- `pythonista_job_runner/tests/test_screenshot_filename_contract.py`

Out of scope for this step: runtime Python job execution internals, Web UI behaviour, and custom integration behaviour except where packaging/security declarations directly depend on them.

## Files reviewed
- `pythonista_job_runner/config.yaml`
- `pythonista_job_runner/build.yaml`
- `pythonista_job_runner/apparmor.txt`
- `pythonista_job_runner/Dockerfile`
- `pythonista_job_runner/run.sh`
- `repository.yaml`
- `.github/workflows/lint.yml`
- `pythonista_job_runner/tests/test_addon_packaging_guardrails.py`
- `pythonista_job_runner/tests/test_docs_links_exist.py`
- `pythonista_job_runner/tests/test_readme_screenshot_assets.py`
- `pythonista_job_runner/tests/test_screenshot_filename_contract.py`

## Validation context
Commands run during this review:
- `pytest -q pythonista_job_runner/tests/test_addon_packaging_guardrails.py pythonista_job_runner/tests/test_docs_links_exist.py pythonista_job_runner/tests/test_readme_screenshot_assets.py pythonista_job_runner/tests/test_screenshot_filename_contract.py` (pass)
- `python -m pip install -q pyyaml && python - <<'PY' ... PY` to parse and syntax-check `config.yaml`, `build.yaml`, `repository.yaml`, and `.github/workflows/lint.yml` with `yaml.safe_load_all` (pass)

No production code changes were made in this review run.

## Findings

### S07-H-01 — Configurable runner bind port conflicts with fixed packaging wiring
- **Severity**: High
- **File/region**:
  - `pythonista_job_runner/config.yaml` (`options.runner.bind_port`, `ingress_port`, `ports`)
  - `pythonista_job_runner/Dockerfile` (`HEALTHCHECK` targeting `localhost:8787`)
- **Issue**:
  The add-on declares a user-configurable `runner.bind_port`, but packaging contracts are fixed to 8787:
  - ingress is pinned to `ingress_port: 8787`
  - direct port exposure is pinned to `8787/tcp`
  - container healthcheck probes `http://localhost:8787/health`

  If `runner.bind_port` is changed from 8787, the runtime listener can drift from the fixed ingress/direct/health endpoints.
- **Why it matters**:
  This creates a realistic breakage path where startup appears successful but ingress/direct access and/or health monitoring fail. In Home Assistant environments, failing healthchecks can trigger unstable lifecycle behaviour and difficult-to-diagnose restarts.
- **Evidence/reasoning**:
  Static inspection shows fixed 8787 values in packaging metadata and Docker healthcheck while `runner.bind_port` remains schema-configurable (`port`). No guardrail test currently enforces this invariant.
- **Recommended narrow fix (apply pass)**:
  Choose one consistent contract:
  1. **Preferred**: remove user configurability for `runner.bind_port` (or hard-fail when not 8787), keeping add-on transport wiring fixed and explicit.
  2. Alternative: plumb bind-port value through all dependent packaging surfaces (ingress/ports/healthcheck) and ensure supported behaviour is explicit.
- **Tests to add/update (apply pass)**:
  - Add packaging guardrail asserting declared runner bind-port contract matches ingress/ports/healthcheck contract.
  - Add a startup/contract test that fails if `runner.bind_port` can diverge from 8787 without coordinated metadata updates.

### S07-M-01 — Dockerfile pins exact Alpine package revisions, increasing build fragility
- **Severity**: Medium
- **File/region**: `pythonista_job_runner/Dockerfile` (`apk add` lines for `cpulimit`, `curl`, `zip`)
- **Issue**:
  `apk add` uses exact revision pinning (`cpulimit=0.2-r3`, `curl=8.14.1-r2`, `zip=3.0-r13`). Exact Alpine revision pins are prone to repository churn and can fail builds when upstream package revisions are superseded or removed.
- **Why it matters**:
  Build reproducibility intent is good, but this pattern can break CI/release unexpectedly on base-image updates or mirror churn, producing avoidable operational failures in packaging pipeline.
- **Evidence/reasoning**:
  Exact `pkg=ver-rev` constraints are visible in Dockerfile and there is no fallback strategy in workflow automation.
- **Recommended narrow fix (apply pass)**:
  Prefer one of:
  1. Pin major/minor policy via base image and install without exact `-rN` revision pins.
  2. If strict pinning is required, add automated dependency refresh workflow and explicit fail-fast documentation for pin maintenance.
- **Tests to add/update (apply pass)**:
  - Add a guardrail test to enforce the selected package pinning policy (either exact pins + maintenance metadata, or unpinned revisions).

### S07-M-02 — CI test matrix omits root-level repository tests, leaving packaging/repo regressions undetected in default pytest job
- **Severity**: Medium
- **File/region**: `.github/workflows/lint.yml` (`pytest` job)
- **Issue**:
  The `pytest` job executes from `cd pythonista_job_runner` and runs only that subtree’s tests. Root-level test suites (including custom integration tests under `tests/`) are excluded from this default job.
- **Why it matters**:
  This creates a CI blind spot where repository-level regressions can merge despite a green `pytest` job, increasing risk of release-time failures or missed cross-surface contract breaks.
- **Evidence/reasoning**:
  Workflow step explicitly changes directory before running `pytest -q`; other jobs run targeted subsets and do not replace full root-level coverage.
- **Recommended narrow fix (apply pass)**:
  Run full repository tests from repo root in the main pytest job (or add a separate explicit root-test job) while keeping targeted jobs for faster diagnostics.
- **Tests to add/update (apply pass)**:
  - Add/adjust CI workflow validation test (if present) to assert at least one CI job runs root-level `pytest -q`.

### S07-L-01 — Packaging guardrail tests rely on ad-hoc YAML string parsing helpers
- **Severity**: Low
- **File/region**: `pythonista_job_runner/tests/test_addon_packaging_guardrails.py` (`_top_level_yaml_list_items`, `_top_level_yaml_map_keys`)
- **Issue**:
  Current guardrail helpers parse YAML using indentation/string heuristics. They are lightweight but can silently mis-handle valid YAML variations (comments, formatting changes, anchors/multiline constructs), reducing reliability of packaging checks.
- **Why it matters**:
  Over time, formatting-only edits can produce false negatives/positives, weakening trust in guardrail outcomes and increasing maintenance burden.
- **Evidence/reasoning**:
  Helpers assume simple top-level list/map formatting and do not parse YAML AST.
- **Recommended narrow fix (apply pass)**:
  Use a YAML parser in tests (`PyYAML` or `ruamel.yaml`) for these assertions to validate semantic structure rather than formatting.
- **Tests to add/update (apply pass)**:
  - Replace helper-implementation-coupled assertions with semantic YAML key/value checks.
  - Add one fixture-like test case that proves comments/ordering/spacing variations do not break guardrail logic.

## Positive observations
- Packaging alignment guardrails already exist for key claims: `config.yaml` architecture declarations vs `build.yaml` `build_from` keys and base-image namespace checks.
- Security-sensitive metadata is explicit in add-on config (`apparmor: true`, non-privileged flags, ingress settings), reducing ambiguity for operators.
- AppArmor profile includes explicit deny rules for high-risk kernel/memory interfaces (`/dev/mem`, `/dev/kmem`, `/dev/port`, `/proc/kcore`) and includes required S6 overlay allowances; this is a solid baseline for constrained add-on execution.
- Workflow has dedicated targeted jobs (`addon-linter`, `yamllint`, `hadolint`, docs guardrails, packaging guardrails), which improves signal granularity when failures occur.

## Apply guidance (for later apply-only pass)
Recommended fix order to reduce risk and rework:
1. **S07-H-01 first**: decide and enforce single bind-port contract across config, ingress, exposed ports, and healthcheck.
2. **S07-M-02 second**: close CI coverage gap by ensuring root-level test execution in workflow.
3. **S07-M-01 third**: settle package pinning policy and encode guardrail expectations.
4. **S07-L-01 last**: refactor packaging test parsing to semantic YAML loading.

After applying fixes, rerun at least:
- packaging/doc guardrails used in this review
- workflow-relevant test target(s)
- add-on linter + Dockerfile lint checks in CI context
