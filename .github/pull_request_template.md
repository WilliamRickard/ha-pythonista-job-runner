<!-- Version: 0.6.12-docs.10 -->
## What changed

-

## Why

-

## Checklist

- [ ] [`pythonista_job_runner/config.yaml`](../pythonista_job_runner/config.yaml) version bumped if behaviour changed
- [ ] [`pythonista_job_runner/CHANGELOG.md`](../pythonista_job_runner/CHANGELOG.md) updated if behaviour changed
- [ ] Documentation updated if user-facing behaviour changed:
  - [ ] [`README.md`](../README.md)
  - [ ] [`pythonista_job_runner/README.md`](../pythonista_job_runner/README.md)
  - [ ] [`pythonista_job_runner/DOCS.md`](../pythonista_job_runner/DOCS.md)
  - [ ] [`SECURITY.md`](../SECURITY.md), if access control or trust boundaries changed
  - [ ] [`docs/RELEASE_CHANNELS.md`](../docs/RELEASE_CHANNELS.md), if release-channel guidance changed
- [ ] Tests are green (`python -m pytest -q`) or rationale given if not applicable
- [ ] If Markdown or screenshots changed, `python -m pytest -q pythonista_job_runner/tests/test_docs_links_exist.py pythonista_job_runner/tests/test_readme_screenshot_assets.py pythonista_job_runner/tests/test_screenshot_filename_contract.py` passed
- [ ] If Web UI sources changed, `python pythonista_job_runner/app/webui_build.py --check` passed
- [ ] Verified in Home Assistant with a basic smoke test where practical
- [ ] No secrets or tokens committed

## How to test

1.
2.
3.

## Evidence

- Logs, screenshots, or reproduction notes:
