<!-- Version: 0.6.12-docs.4 -->
# Contributing

Thanks for contributing.

## Ground rules

- Use pull requests (even for small changes).
- Keep changes focused and easy to review.
- Do not commit tokens, passwords, or any other secrets.
- Prefer behaviour-preserving fixes over refactors.

## Versioning

- If you change add-on behaviour, bump the add-on version in [`pythonista_job_runner/config.yaml`](pythonista_job_runner/config.yaml) and add an entry to [`pythonista_job_runner/CHANGELOG.md`](pythonista_job_runner/CHANGELOG.md).
- If you only change documentation, you normally do not need to bump the add-on version.

## Documentation

- Home Assistant shows [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md) in the add-on Documentation tab. Treat that file as the primary user guide.
- Start with the repository [`README.md`](README.md) for the quick project overview, then use [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md) for the full user guide.
- Keep examples runnable and avoid assumptions about the user environment.

Markdown version headers:

- Most Markdown files in this repo use a `<!-- Version: ... -->` header on line 1. If you make a meaningful change, bump the version.
- The Web UI part READMEs are intentionally versionless and must stay that way:
  - [`pythonista_job_runner/app/webui_html/README.md`](pythonista_job_runner/app/webui_html/README.md)
  - [`pythonista_job_runner/app/webui_css/README.md`](pythonista_job_runner/app/webui_css/README.md)
  - [`pythonista_job_runner/app/webui_js/README.md`](pythonista_job_runner/app/webui_js/README.md)
  The Web UI build will fail if any of those files contains a `<!-- Version: ... -->` line.

## Web UI build

The Ingress Web UI is shipped as a single generated file ([`pythonista_job_runner/app/webui.html`](pythonista_job_runner/app/webui.html)) for reliability behind the Home Assistant Ingress path prefix. Do not hand-edit the generated outputs.

Source inputs:

- HTML wrapper: [`pythonista_job_runner/app/webui_src.html`](pythonista_job_runner/app/webui_src.html)
- HTML partials: [`pythonista_job_runner/app/webui_html/`](pythonista_job_runner/app/webui_html/) (`*.html`)
- CSS partials: [`pythonista_job_runner/app/webui_css/`](pythonista_job_runner/app/webui_css/) (`*.css`)
- JavaScript parts: [`pythonista_job_runner/app/webui_js/`](pythonista_job_runner/app/webui_js/) (`*.js`)

Generated outputs:

- [`pythonista_job_runner/app/webui.html`](pythonista_job_runner/app/webui.html)
- [`pythonista_job_runner/app/webui.css`](pythonista_job_runner/app/webui.css)
- [`pythonista_job_runner/app/webui.js`](pythonista_job_runner/app/webui.js)

Rebuild:

- `python pythonista_job_runner/app/webui_build.py`

Check that generated outputs are up to date (used by tests):

- `python pythonista_job_runner/app/webui_build.py --check`

If you add, remove, or rename a part file, you must update the explicit ordered lists in [`pythonista_job_runner/app/webui_build.py`](pythonista_job_runner/app/webui_build.py):

- `WEBUI_HTML_PARTS`
- `WEBUI_CSS_PARTS`
- `WEBUI_JS_PARTS`

Build guardrails enforced by [`webui_build.py`](pythonista_job_runner/app/webui_build.py):

- HTML partials must not contain document-level tags (`<!doctype>`, `<html>`, `<head>`, `<body>`) or `<script>` or `<style>` blocks.
- HTML `id` attributes must be unique across all HTML partials.
- Root-relative URLs are forbidden in HTML, CSS, and JavaScript (for example `href="/..."`, `url(/...)`, `fetch("/...")`).
- JavaScript part files must not contain their own `VERSION:` headers.
- `WEBUI_VERSION` is the single source of truth for Web UI versioning. The build checks version headers in `webui_src.html`, `webui.html`, `webui.css`, and `webui.js`.

## Testing

This repo includes a lightweight test suite under `pythonista_job_runner/tests`.

Typical local checks:

1. Run unit tests:
   - `python -m pytest -q`

2. If you changed the Web UI sources, also run:
   - `python pythonista_job_runner/app/webui_build.py --check`

3. Manual smoke test (recommended):
   - Jobs list loads
   - Details view loads
   - Logs stream correctly
   - Downloads work

## Releases

This repository is intended to be installed as a third-party repository in Home Assistant. Home Assistant will build the add-on image from the contents of `pythonista_job_runner/` when the user installs or updates it.
