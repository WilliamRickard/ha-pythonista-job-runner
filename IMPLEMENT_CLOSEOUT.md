# IMPLEMENT_CLOSEOUT.md

## Targeted repair note (current pass)

- Root cause confirmed: `pythonista_job_runner/app/http_api_server.py` had three stray pasted lines (`from http_api_auth import auth_ok, client_ip`, a comment, and `j = runner.new_job(...)`) injected inside `_handle_run_post()` after the `incomplete_upload` branch. This both removed the required `return` after that error response and introduced an indentation break at the following `try:` block, causing `IndentationError` during compilation.

## Remaining gaps found

The following gaps were originally identified during review; the first group have been addressed in this PR and are retained here as historical notes.

### Previously identified gaps (addressed in this PR)

1. Leftover artefact: `pythonista_job_runner/app/runner_core.py.bak` (now deleted).
2. `pythonista_job_runner/app/http_api_server.py` was monolithic (~437 lines) and mixed routing, auth, body parsing, and response writing (now decomposed into helpers with stable behaviour).
3. Architecture messaging overstated confidence: docs implied full support for `amd64`, `aarch64`, and `armv7`, but repo-level proof was mainly config/build declarations and not execution on all targets (now clarified and guarded in docs/CI).

### Remaining gaps

1. API contract/client sync can be tightened around negative cases and explicit response semantics.
2. Security/negative-path coverage is good but can be strengthened for additional request validation edge cases.
3. CI guardrails can better catch architecture-claim drift and API-contract drift against docs messaging.
4. Changelog/docs need a truthfulness sweep for close-out status and caveats.
## Ordered milestones

1. **Close obvious artefacts and create low-risk HTTP API decomposition**
   - Delete backup file.
   - Extract HTTP API helpers (routing/auth/validation/responses) into focused modules.
   - Keep wire behaviour stable.
2. **Strengthen backend negative-path tests**
   - Add tests for content-type validation, malformed purge/run payloads, and error-code handling.
3. **Contract/client alignment**
   - Ensure OpenAPI documents the implemented statuses and payloads.
   - Add client tests for surfaced error semantics and timeout/JSON failure handling.
4. **Truthful architecture + docs/changelog guardrails**
   - Rewrite architecture claims to be precise about what is declared vs. validated in CI.
   - Add/adjust tests so docs/config drift is caught.
5. **Final validation + close-out**
   - Run focused tests first, then full required commands.
   - Final truthfulness sweep.

## Validation commands by milestone

- Milestone 1:
  - `cd pythonista_job_runner && pytest -q tests/test_http_api_basic.py tests/test_http_api_lifecycle_integration.py`
- Milestone 2:
  - `cd pythonista_job_runner && pytest -q tests/test_http_api_basic.py tests/test_utils_zip_extract.py`
- Milestone 3:
  - `cd pythonista_job_runner && pytest -q tests/test_api_contract.py tests/test_pythonista_client.py`
- Milestone 4:
  - `cd pythonista_job_runner && pytest -q tests/test_addon_packaging_guardrails.py tests/test_docs_links_exist.py`
- Milestone 5 (required):
  - `cd pythonista_job_runner && python app/webui_build.py --check`
  - `cd pythonista_job_runner && pytest -q`

## Checklist

- [x] Baseline test run completed once before changes.
- [x] Remove backup/junk artefacts.
- [x] Decompose HTTP API server with stable behaviour.
- [x] Add/adjust backend security and negative-path tests.
- [x] Align OpenAPI + Pythonista client + examples.
- [x] Reassess/tighten web UI mobile/a11y/detail states if gaps remain.
- [x] Correct architecture claims or add precise caveats + guardrails.
- [x] Update docs/changelog for truthfulness.
- [x] Run required final validations.
- [x] Commit changes.
- [x] Create PR message via `make_pr`.
