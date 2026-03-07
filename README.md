<!-- Version: 0.6.12-docs.6 -->
# Pythonista Job Runner (Home Assistant add-on repository)

Run Python jobs from Pythonista (iOS) on your Home Assistant host, and download the results as a zip. The add-on includes an Ingress Web UI for job status and logs.

For the full guide (configuration, API reference, Pythonista client examples, troubleshooting), see [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md).

[![Add this add-on repository to your Home Assistant instance](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FWilliamRickard%2Fha-pythonista-job-runner)
[![Open the add-on in Home Assistant](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=pythonista_job_runner)

## Quick start (five minutes)

1. Add this repository to Home Assistant (use the button above, or follow the manual steps below).
2. In Settings -> Add-ons -> Add-on Store, find **Pythonista Job Runner**, install it, then open it.
3. In the add-on configuration, set a strong **Access token** and save.
4. Start the add-on.
5. From Pythonista, upload a job zip to `http://YOUR_HOME_ASSISTANT_HOST:8787/run` with header `X-Runner-Token: YOUR_RUNNER_TOKEN`. This direct API path only works when **Access token** is set and **Ingress only** is off.

If you want to confirm the add-on is working before touching Pythonista, open **Open Web UI** (Ingress) and check that the job list loads.

## Contents

- [Install this repository in Home Assistant](#install-this-repository-in-home-assistant)
- [Install and configure the add-on](#install-and-configure-the-add-on)
- [Run your first job from Pythonista](#run-your-first-job-from-pythonista)
- [Screenshots](#screenshots)
- [Security model](#security-model)
- [Troubleshooting](#troubleshooting)
- [Documentation map](#documentation-map)
- [Support](#support)

## Install this repository in Home Assistant

Option A (recommended): My Home Assistant link

Use the button at the top of this README.

Option B: manual

1. In Home Assistant, go to Settings -> Add-ons -> Add-on Store.
2. Open the top-right menu (three dots) -> Repositories.
3. Add:
   `https://github.com/WilliamRickard/ha-pythonista-job-runner`

## Install and configure the add-on

## Supported architectures

This repository currently **declares** these Home Assistant add-on architectures:

- `amd64`
- `aarch64`
- `armv7`

`config.yaml` and `build.yaml` are kept in lockstep and point to Home Assistant base Python images for the same architecture keys. CI validates this declaration alignment and packaging consistency.

Important truthfulness note: the automated test suite in this repository executes on `amd64` CI runners. For `aarch64` and `armv7`, this repository currently validates build metadata and image selection, but does not run full runtime integration tests on native hardware in CI.


1. In the Add-on Store, open **Pythonista Job Runner** and install it.
2. Open the add-on configuration:
   - Set **Access token** to a long, random value
   - Save
3. Start the add-on.
4. Optional: open **Open Web UI** to confirm the Ingress UI loads.

The external HTTP API listens on port 8787 on your Home Assistant host.

## Run your first job from Pythonista

### Job zip format

Your upload is a zip file with `run.py` at the zip root. Anything else in the zip is unpacked next to it and is available to your script.

Your script can write output files under an `outputs/` directory. Those files are included in the result zip.

### Minimal run.py

```python
import os

print("Hello from the Home Assistant add-on")

os.makedirs("outputs", exist_ok=True)
with open("outputs/hello.txt", "w", encoding="utf-8") as f:
    f.write("It worked.\n")
```

When the job completes, the add-on returns a result zip that always includes `stdout.txt`, `stderr.txt`, and `status.json`. If your script wrote files under `outputs/`, they are included too.

### Minimal Pythonista upload example

This creates a tiny job zip in memory, uploads it, and saves the returned result zip next to the script as `result.zip`.

```python
import io
import zipfile

import requests

HOST = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(
        "run.py",
        """import os
print('Hello from Pythonista')
os.makedirs('outputs', exist_ok=True)
with open('outputs/hello.txt', 'w', encoding='utf-8') as f:
    f.write('It worked.\n')
        """,
    )

payload = buf.getvalue()
r = requests.post(
    f"{HOST}/run",
    headers={
        "X-Runner-Token": TOKEN,
        "Content-Type": "application/zip",
    },
    data=payload,
    timeout=60,
)
r.raise_for_status()

with open("result.zip", "wb") as f:
    f.write(r.content)

print("Saved result.zip")
```

For a fuller client (stream logs, cancel jobs, download results by job id), see [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md).

## Screenshots

The repo now includes placeholder screenshots in [`docs/screenshots/`](docs/screenshots/) so the README layout works before real captures are added. Replace them with current Home Assistant screenshots when the UI is ready.

### Add-on Store entry

![Home Assistant Add-on Store page for Pythonista Job Runner](docs/screenshots/01_addon_store.png)

### Add-on configuration

![Pythonista Job Runner configuration page showing the access token setting](docs/screenshots/02_config_token.png)

### Ingress Web UI

![Pythonista Job Runner Ingress Web UI showing the jobs list](docs/screenshots/03_webui_jobs.png)

## Security model

- `GET /health` is intentionally unauthenticated for basic connectivity checks.
- The Ingress Web UI runs inside Home Assistant and uses Home Assistant authentication. It does not use `X-Runner-Token`.
- Direct API requests from Pythonista must send `X-Runner-Token`. If **Access token** is blank, direct API access is disabled.
- If **Allowed client CIDRs** is set, direct API requests must come from an allowed network as well as present the correct token.
- If **Ingress only** (`ingress_strict`) is enabled, direct API access is blocked completely, even with the right token and CIDR.
- Keep port `8787` on your local network only. Do not expose it to the public internet.

For more detail and hardening ideas, see [`SECURITY.md`](SECURITY.md).

## Troubleshooting

- **401 unauthorised**: check the token, confirm **Access token** is not blank, and make sure **Ingress only** is off if you are calling the direct API from Pythonista.
- **Cannot connect**: confirm the add-on is started and that `YOUR_HOME_ASSISTANT_HOST` is reachable from your iPhone.
- **Upload fails immediately**: your zip must contain `run.py` at the zip root (not inside a subfolder).
- **Result zip is missing your files**: your script must write them under `outputs/`.

More troubleshooting is in [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md).

## Documentation map

- [`README.md`](README.md) (this file): quick start
- [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md): full user guide and API reference
- [`pythonista_job_runner/README.md`](pythonista_job_runner/README.md): short add-on intro
- [`SECURITY.md`](SECURITY.md): security model and safe setup

## Development

Contributor guide: see [`CONTRIBUTING.md`](CONTRIBUTING.md).

Web UI sources live under `pythonista_job_runner/app/`:

- HTML wrapper: [`webui_src.html`](pythonista_job_runner/app/webui_src.html)
- HTML partials: [`webui_html/*.html`](pythonista_job_runner/app/webui_html/)
- CSS partials: [`webui_css/*.css`](pythonista_job_runner/app/webui_css/)
- JavaScript parts: [`webui_js/*.js`](pythonista_job_runner/app/webui_js/)

Generated outputs (do not edit by hand):

- [`webui.html`](pythonista_job_runner/app/webui.html), [`webui.css`](pythonista_job_runner/app/webui.css), [`webui.js`](pythonista_job_runner/app/webui.js)

Rebuild and validate:

- `python pythonista_job_runner/app/webui_build.py`
- `python pythonista_job_runner/app/webui_build.py --check`

## Support

- For usage and troubleshooting, start with [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md).
- For bugs and feature requests, open a GitHub issue in this repository.


## Platform hardening notes

- Add-on ingress now enables streamed uploads (`ingress_stream: true`) for safer large payload handling through Home Assistant ingress.
- A custom `apparmor.txt` profile is included and the add-on config explicitly declares non-privileged runtime flags.
- Job and control actions are written to `/data/audit_events.jsonl` with ingress identity metadata when Home Assistant provides `X-Remote-User-*` headers.
- Companion Home Assistant integration is available under `custom_components/pythonista_job_runner` with sensors, system health, and repair issue hooks.


## Release channels

This repository supports two usage channels:

- **Stable**: the `main` branch and tagged releases.
- **Next/Canary**: the `next` branch for pre-release validation and breaking-change soak.

See [docs/RELEASE_CHANNELS.md](docs/RELEASE_CHANNELS.md) for the operational process and user guidance.


## Diagnostics and support bundle

The add-on exposes a redacted support-bundle endpoint at `/support_bundle.json` (requires token auth). It includes configuration summary, stats, queue/job metadata, and recent audit events while excluding secrets and raw outputs.
