# Changelog

## Unreleased

- Repository scaffold added: CI linting, issue templates, PR checklist.

## 0.6.3

- Fix runner_core missing imports that could crash on job completion (result zip, notifications).
- Wire up install_requirements and pip_* options (per-job pip install into work/_deps, adds to PYTHONPATH).
- Wire up cleanup_min_free_mb (best-effort deletion of oldest finished jobs when disk is low).
- Fix duplicate ip_in_cidrs definition in utils.
- Preserve job ordering across restarts.
- Add GitHub Actions job to run pytest.

## 0.6.2

- Fix add-on startup crash (ensure runner_core imports dataclasses and utc_now/parse_utc).
- Bump add-on version to force Home Assistant rebuild.

## 0.6.1

- Fix add-on startup crash (NameError: field is not defined).

## 0.6.0

- Web UI improvements, stats, notifications, modularised server code.
