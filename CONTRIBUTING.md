<!-- Version: 0.6.12-docs.7 -->
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

## Documentation maintenance

Use the docs files for different jobs so they do not drift into copies of each other:

- [`README.md`](README.md): repository overview, Home Assistant repository install, first successful run, and top-level screenshots. Update this when the first-run path or repository-level positioning changes.
- [`pythonista_job_runner/README.md`](pythonista_job_runner/README.md): short add-on introduction. Keep it brief and focused on what the add-on does and the fastest route to success.
- [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md): full user guide. Update this for configuration, API behaviour, Pythonista examples, troubleshooting, and advanced usage.
- [`SECURITY.md`](SECURITY.md): token, Ingress, direct API, CIDR allowlist, and execution-user security behaviour. Update this whenever access control or trust boundaries change.
- [`pythonista_job_runner/CHANGELOG.md`](pythonista_job_runner/CHANGELOG.md): user-visible behaviour, documentation, and repo hygiene changes worth calling out in a release note.
- [`docs/screenshots/README.md`](docs/screenshots/README.md): screenshot purpose, filenames, and replacement guidance. Update this when screenshot filenames or capture expectations change.

Before you finish a docs change, check whether the same behaviour is described in more than one file and make sure the short files point to the detailed file instead of repeating it.

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
- `WEBUI_VERSION` is the single source of truth for Web UI versioning. The build checks version headers in [`pythonista_job_runner/app/webui_src.html`](pythonista_job_runner/app/webui_src.html), [`pythonista_job_runner/app/webui.html`](pythonista_job_runner/app/webui.html), [`pythonista_job_runner/app/webui.css`](pythonista_job_runner/app/webui.css), and [`pythonista_job_runner/app/webui.js`](pythonista_job_runner/app/webui.js).

## Testing

This repo includes a lightweight test suite under `pythonista_job_runner/tests`.

Typical local checks:

1. Run unit tests:
   - `python -m pytest -q`

2. If you changed the Web UI sources, also run:
   - `python pythonista_job_runner/app/webui_build.py --check`

3. If you changed Markdown, internal doc links, or screenshots, also run:
   - `python -m pytest -q pythonista_job_runner/tests/test_docs_links_exist.py pythonista_job_runner/tests/test_readme_screenshot_assets.py pythonista_job_runner/tests/test_screenshot_filename_contract.py`

4. Manual smoke test (recommended):
   - Jobs list loads
   - Details view loads
   - Logs stream correctly
   - Downloads work

## Releases

This repository is intended to be installed as a third-party repository in Home Assistant. Home Assistant will build the add-on image from the contents of `pythonista_job_runner/` when the user installs or updates it.

## Updating screenshots

When you replace the placeholder images under [`docs/screenshots/`](docs/screenshots/):

- Prefer PNG.
- Aim for roughly 1200 to 1600 pixels wide so the image still reads clearly in GitHub and on phones.
- Crop tightly so the important controls are legible.
- Check for tokens, usernames, IP addresses, hostnames, file paths, repository URLs, or other sensitive details before you commit.
- Keep the approved screenshot filenames stable unless the screenshot purpose changes, because the root [`README.md`](README.md) links to those names directly.

The screenshot filenames are a contract between [`README.md`](README.md), [`docs/screenshots/README.md`](docs/screenshots/README.md), and the actual PNG files in [`docs/screenshots/`](docs/screenshots/). If you add, remove, or rename an embedded screenshot, update all three in the same change.

## Generated artefacts and caches

Do not commit packaging artefacts or local test caches. In particular:

- `PR_METADATA.json`
- `CHANGES_MANIFEST.json`
- `.pytest_cache/`
- `__pycache__/`

These files are not part of the add-on source and make review noisier.
