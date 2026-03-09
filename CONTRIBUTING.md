<!-- Version: 0.6.12-docs.10 -->
# Contributing

Thanks for contributing.

Please follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) in all project spaces.

## Ground rules

- Use pull requests, even for small changes.
- Keep changes focused and easy to review.
- Do not commit tokens, passwords, or any other secrets.
- Prefer behaviour-preserving fixes over broad refactors unless the refactor is the point of the change.

## Versioning

- If you change add-on behaviour, bump the add-on version in [`pythonista_job_runner/config.yaml`](pythonista_job_runner/config.yaml) and add an entry to [`pythonista_job_runner/CHANGELOG.md`](pythonista_job_runner/CHANGELOG.md).
- If you only change documentation, you normally do not need to bump the add-on version.

## Documentation layout

Use the docs files for different jobs so they do not drift into copies of each other.

- [`README.md`](README.md): repository landing page and fastest route to first success.
- [`pythonista_job_runner/README.md`](pythonista_job_runner/README.md): short add-on summary for store-style viewing.
- [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md): canonical user guide, Pythonista examples, troubleshooting, and API reference.
- [`SECURITY.md`](SECURITY.md): access model, trust boundaries, and safe operating guidance.
- [`docs/RELEASE_CHANNELS.md`](docs/RELEASE_CHANNELS.md): stable versus next guidance.
- [`docs/screenshots/README.md`](docs/screenshots/README.md): screenshot filename contract and replacement guidance.

When behaviour is described in more than one place, keep the short files short and push the detail into [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md).

## Markdown version headers

Most Markdown files in this repo use a `<!-- Version: ... -->` header on line 1. If you make a meaningful change, bump the version.

The Web UI part READMEs are intentionally versionless and must stay that way:

- [`pythonista_job_runner/app/webui_html/README.md`](pythonista_job_runner/app/webui_html/README.md)
- [`pythonista_job_runner/app/webui_css/README.md`](pythonista_job_runner/app/webui_css/README.md)
- [`pythonista_job_runner/app/webui_js/README.md`](pythonista_job_runner/app/webui_js/README.md)

The Web UI build fails if any of those files contains a version header.

## Issue forms and pull requests

Use the GitHub issue forms for bugs, support questions, feature requests, and docs feedback.

The pull request template expects you to update the user docs when user-facing behaviour changes.

## Web UI build

The Ingress Web UI is shipped as a single generated file, [`pythonista_job_runner/app/webui.html`](pythonista_job_runner/app/webui.html), for reliability behind the Home Assistant Ingress path prefix. Do not hand-edit the generated outputs.

Source inputs:

- HTML wrapper: [`pythonista_job_runner/app/webui_src.html`](pythonista_job_runner/app/webui_src.html)
- HTML partials: [`pythonista_job_runner/app/webui_html/`](pythonista_job_runner/app/webui_html/)
- CSS partials: [`pythonista_job_runner/app/webui_css/`](pythonista_job_runner/app/webui_css/)
- JavaScript parts: [`pythonista_job_runner/app/webui_js/`](pythonista_job_runner/app/webui_js/)

Generated outputs:

- [`pythonista_job_runner/app/webui.html`](pythonista_job_runner/app/webui.html)
- [`pythonista_job_runner/app/webui.css`](pythonista_job_runner/app/webui.css)
- [`pythonista_job_runner/app/webui.js`](pythonista_job_runner/app/webui.js)

Rebuild:

- `python pythonista_job_runner/app/webui_build.py`

Check that generated outputs are up to date:

- `python pythonista_job_runner/app/webui_build.py --check`

If you add, remove, or rename a part file, update the explicit ordered lists in [`pythonista_job_runner/app/webui_build.py`](pythonista_job_runner/app/webui_build.py).

## Testing

Typical local checks:

1. Run unit tests:
   - `python -m pytest -q`
2. If you changed the Web UI sources, also run:
   - `python pythonista_job_runner/app/webui_build.py --check`
3. If you changed Markdown, also run:
   - `python -m pytest -q pythonista_job_runner/tests/test_docs_links_exist.py pythonista_job_runner/tests/test_readme_screenshot_assets.py pythonista_job_runner/tests/test_screenshot_filename_contract.py`
4. Do a manual smoke test in Home Assistant when practical.

## Updating screenshots

When you replace the placeholder images under [`docs/screenshots/`](docs/screenshots/):

- prefer PNG
- aim for roughly 1200 to 1600 pixels wide
- crop tightly so the important controls are legible
- check for tokens, usernames, IP addresses, hostnames, file paths, or repository URLs before committing
- keep approved filenames stable unless the screenshot purpose changes

The screenshot filenames are a contract between [`README.md`](README.md), [`docs/screenshots/README.md`](docs/screenshots/README.md), and the actual PNG files in [`docs/screenshots/`](docs/screenshots/).

## Generated artefacts and caches

Do not commit packaging artefacts or local test caches.
