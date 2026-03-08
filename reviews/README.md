# Code Review Artefacts

This directory stores per-slice review artefacts for the Pythonista Job Runner review programme.

## Process

Each slice has two documents:

1. **Review-only file** (`Sxx_*_review.md`)
   - No production-code edits in this pass.
   - Records findings and no-finding justifications.
2. **Apply-only file** (`Sxx_*_apply.md`)
   - Tracks fixes applied from the review file.
   - Must map each change back to finding IDs.

Review-only and apply-only work must remain separated.

## Severity levels

- **Critical**: immediate security/data-loss/system integrity risk; exploit or failure path is direct.
- **High**: significant correctness/safety failure likely in normal or stressed operation.
- **Medium**: real reliability/maintainability risk that can become production impact.
- **Low**: code quality, readability, test coverage, or hygiene issue with limited immediate impact.

## Finding entry format

Each finding should include:
- ID (`Sxx-C-01`, `Sxx-H-01`, `Sxx-M-01`, `Sxx-L-01`)
- Title
- Exact file and function/class/region
- Impact and risk category
- Evidence (repro or static reasoning)
- Recommended narrow fix direction
- Test impact (what to add/update)

“No finding” sections are allowed when explicitly justified.

## Derived artefacts note

Generated Web UI outputs are derived artefacts and are not primary review targets:
- `pythonista_job_runner/app/webui.js`
- `pythonista_job_runner/app/webui.css`
- `pythonista_job_runner/app/webui.html`

Review source/generator paths first, then verify generated drift.
