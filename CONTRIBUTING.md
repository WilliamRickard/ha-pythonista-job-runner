<!-- Version: 0.6.12-docs.1 -->
# Contributing

Thanks for contributing.

## Ground rules

- Use pull requests (even for small changes).
- Keep changes focused and easy to review.
- Do not commit tokens, passwords, or any other secrets.
- Prefer behaviour-preserving fixes over refactors.

## Versioning

- If you change add-on behaviour, bump the add-on version in `pythonista_job_runner/config.yaml` and add an entry to `pythonista_job_runner/CHANGELOG.md`.
- If you only change documentation, you normally do not need to bump the add-on version.

## Documentation

- The add-on UI shows `pythonista_job_runner/DOCS.md` in the Documentation tab.
- Keep examples runnable and avoid assumptions about the user environment.
- When editing Markdown files in this repo, keep the `<!-- Version: ... -->` header on line 1 and bump it when you make a meaningful change.

## Testing

This repo includes a lightweight test suite under `pythonista_job_runner/tests`.

Typical local checks:

1. Run unit tests:
   - `python -m pytest -q`
2. If you changed the Web UI, open the add-on and confirm:
   - Jobs list loads
   - Details view loads
   - Logs stream correctly
   - Downloads work

## Releases

This repository is intended to be installed as a third-party repository in Home Assistant. Home Assistant will build the add-on image from the contents of `pythonista_job_runner/` when the user installs or updates it.
