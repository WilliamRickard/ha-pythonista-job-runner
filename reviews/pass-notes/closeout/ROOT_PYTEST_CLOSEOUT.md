Version: 0.6.12-root-pytest-closeout.1
# Root Pytest Closeout Plan

Current location: `reviews/pass-notes/closeout/ROOT_PYTEST_CLOSEOUT.md`

## Failing command
- `pytest -q` (run from repository root)

## Confirmed root cause
- `pythonista_job_runner/tests/test_backup_pause_resume.py` read `app/runner_core.py` via a cwd-relative path, which only works when pytest is launched from inside `pythonista_job_runner`.

## Files changed
- `pythonista_job_runner/tests/test_backup_pause_resume.py`
- `ROOT_PYTEST_CLOSEOUT.md`

## Validation commands
- `pytest -q`
- `pytest -q pythonista_job_runner/tests/test_backup_pause_resume.py`
- `cd pythonista_job_runner && python app/webui_build.py --check`
- `cd pythonista_job_runner && node --check app/webui.js`

## Checklist
- [x] Reproduced root-level failure before edits
- [x] Applied minimal cwd-agnostic test fix
- [x] Searched nearby tests for similar cwd assumptions (`rg 'Path\("app/|open\("app/|"app/' pythonista_job_runner/tests -n`)
- [x] Ran narrow validation
- [x] Ran full root-level validation
- [x] Ran web UI build + JS syntax checks
- [x] Truthfulness sweep completed (no pass-note updates required; no repo-level validation claims were overstated in touched notes)
