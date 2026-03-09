<!-- Version: 0.6.12-docs.10 -->
# Screenshot placeholders and replacement guide

This folder holds the screenshots embedded by the repository [`README.md`](../../README.md).

Approved screenshot filenames:

1. [`01_addon_store.png`](01_addon_store.png): Home Assistant Add-on Store entry for Pythonista Job Runner, showing the install button and short description.
2. [`02_config_token.png`](02_config_token.png): add-on configuration page showing the Access token field without a real token.
3. [`03_webui_jobs.png`](03_webui_jobs.png): Ingress Web UI showing the jobs list and at least one completed job.

The repo currently ships placeholder PNGs using those filenames so the root [`README.md`](../../README.md) can embed images immediately. Replace each placeholder with a real screenshot when you have a good capture.

## Capture guidance

- Prefer PNG.
- Aim for roughly 1200 to 1600 pixels wide.
- Crop tightly so the important controls stay readable on mobile.
- Avoid personal information such as hostnames, usernames, IP addresses, tokens, file paths, or repository URLs that are not intended to be public.
- Check that the visible UI text still matches the current add-on before committing a replacement.
- Keep filenames stable unless the screenshot purpose changes.

The docs test suite checks that screenshot files referenced by [`README.md`](../../README.md) exist, have sensible dimensions for GitHub and mobile viewing, use descriptive alt text, and stay in sync with the approved filename list in this file.
