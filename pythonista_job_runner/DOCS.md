<!-- Version: 0.6.12-docs.10 -->
# Pythonista Job Runner

Pythonista Job Runner is a Home Assistant add-on that accepts a job zip, extracts it into an isolated working directory, runs `run.py`, streams logs while it runs, and returns a result zip when it finishes.

It supports two access paths:

- **Ingress Web UI** inside Home Assistant for people using the built-in interface.
- **Direct HTTP API** on port `8787` for Pythonista and other clients.

## Task index

- [Install the repository and add-on](#install-the-repository-and-add-on)
- [Secure the add-on before you use it](#secure-the-add-on-before-you-use-it)
- [First run in the Web UI](#first-run-in-the-web-ui)
- [First run from Pythonista](#first-run-from-pythonista)
- [Ingress versus direct API access](#ingress-versus-direct-api-access)
- [Job zip format](#job-zip-format)
- [Result zip format](#result-zip-format)
- [Pythonista client examples](#pythonista-client-examples)
- [HTTP API reference](#http-api-reference)
- [Troubleshooting](#troubleshooting)
- [Security and operating notes](#security-and-operating-notes)
- [Advanced and contributor notes](#advanced-and-contributor-notes)

## Install the repository and add-on

### Add the repository

1. In Home Assistant, go to **Settings -> Add-ons -> Add-on Store**.
2. Open the top-right menu and choose **Repositories**.
3. Add:
   `https://github.com/WilliamRickard/ha-pythonista-job-runner`

You can also use the My Home Assistant button in the repository [`README.md`](../README.md).

### Install the add-on

1. Find **Pythonista Job Runner** in the add-on store.
2. Install it.
3. Start it.
4. Open **Open Web UI** and confirm the jobs list loads.

## Secure the add-on before you use it

Set these options before you start using the direct API:

- **Access token**: direct API clients such as Pythonista must send this value in the `X-Runner-Token` header.
- **Ingress only**: when enabled, only Home Assistant Ingress can access the add-on. That blocks direct API calls from Pythonista.
- **Allowed client CIDRs**: when set, direct API requests must come from an allowed network as well as present the correct token.

Typical Pythonista setup:

1. Set a strong **Access token**.
2. Leave **Ingress only** off.
3. Optionally set **Allowed client CIDRs** to your local Wi-Fi subnet.

Do not expose port `8787` directly to the public internet. For remote access, use a virtual private network or another trusted path back to your home network.

For the full security model, read [`../SECURITY.md`](../SECURITY.md).

## First run in the Web UI

This is the fastest way to prove the add-on is healthy.

1. Open the add-on in Home Assistant.
2. Click **Open Web UI**.
3. Confirm the jobs list loads.
4. Confirm the UI can refresh without errors.
5. Confirm the settings and help panels open and scroll correctly on your device.

Once that works, the Ingress path is healthy and you can use the Web UI for day-to-day monitoring even if your actual job submission happens from Pythonista.

## First run from Pythonista

The add-on expects a raw zip request body, not a multipart form upload.

Your first job should be tiny. Put `run.py` at the zip root and write a single file under `outputs/`.

### Minimal `run.py`

```python
import os

print("Hello from Pythonista Job Runner")

os.makedirs("outputs", exist_ok=True)
with open("outputs/hello.txt", "w", encoding="utf-8") as f:
    f.write("It worked.
")
```

### Minimal Pythonista upload example

```python
import io
import zipfile

import requests

RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"
REQUEST_TIMEOUT_SECONDS = 60

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(
        "run.py",
        """import os
print('Hello from Pythonista Job Runner')
os.makedirs('outputs', exist_ok=True)
with open('outputs/hello.txt', 'w', encoding='utf-8') as f:
    f.write('It worked.\n')
""",
    )

response = requests.post(
    RUNNER_URL + "/run",
    data=buf.getvalue(),
    headers={
        "X-Runner-Token": TOKEN,
        "Content-Type": "application/zip",
    },
    timeout=REQUEST_TIMEOUT_SECONDS,
)
response.raise_for_status()

with open("result.zip", "wb") as f:
    f.write(response.content)

print("Saved result.zip")
```

A successful first run gives you a result zip that includes `stdout.txt`, `stderr.txt`, `status.json`, and `outputs/hello.txt`.

## Ingress versus direct API access

Use **Ingress** when you are interacting with the built-in Web UI from inside Home Assistant. Use the **direct API** when Pythonista or another client needs to upload a job zip over the network.

### Ingress

Ingress is the simplest path for people using the Web UI:

1. Open the add-on inside Home Assistant.
2. Click **Open Web UI**.
3. Browse jobs, logs, and result downloads from the authenticated Home Assistant session.

Ingress requests are authenticated by Home Assistant itself. You do not send `X-Runner-Token` manually in this flow.

### Direct API

The direct API is the path Pythonista uses. It goes to port `8787` on your Home Assistant host and requires `X-Runner-Token`. It only works when an Access token is set, **Ingress only** is off, and the client IP matches any configured CIDR allowlist.

Rule of thumb:

- Open Web UI inside Home Assistant: use Ingress.
- Upload from Pythonista on your phone: use the direct API.

## Job zip format

Your upload must be a zip file with `run.py` at the root.

- `run.py` is executed as the job entry point.
- Any other files in the zip are extracted into the job working directory.
- Files written under `outputs/` are included in the result zip.

### Optional `requirements.txt`

The add-on can optionally install dependencies listed in `requirements.txt` at the job root into a per-job directory.

This is off by default. To use it:

1. In add-on configuration, enable **Install requirements**.
2. Include `requirements.txt` in the job zip root.

Only enable this when you trust the code you are running.

## Result zip format

When the job completes, the result zip includes:

- `stdout.txt`
- `stderr.txt`
- `status.json`
- `exit_code.txt`
- `summary.txt`
- `result_manifest.json`
- `job.log`
- Optional pip install logs when requirement installation was used
- Your files under `outputs/`, if any

## API contract

The machine-readable direct API contract lives at [`api/openapi.json`](api/openapi.json).

It is intended for client tooling, documentation sync, and regression checks.

## Reusable Pythonista client toolkit

A lightweight client module is provided at [`app/pythonista_client.py`](app/pythonista_client.py).

Key capabilities:

- Upload zip bytes or files
- Poll for completion
- Fetch tail logs
- Cancel or delete jobs
- Download and extract result zips
- Run an end-to-end submit, wait, and collect flow

A runnable example script is included at [`examples/pythonista_run_job.py`](examples/pythonista_run_job.py).

## HTTP API reference

All endpoints are served by the add-on.

### Public endpoints

- `GET /health` returns `{"status": "ok", "version": "<add-on version>"}`.
- `GET /` and `GET /index.html` return JSON info by default. If the client prefers HTML, they return the Web UI and require authentication.
- `GET /info.json` returns the same JSON info as `/`.

### Authenticated endpoints

Send the token in this header:

- `X-Runner-Token: <access token>`

Endpoints:

- `POST /run`: submit a job zip as raw bytes in the request body.
- `GET /jobs.json`: list jobs.
- `GET /job/<job_id>.json`: fetch job status.
- `GET /tail/<job_id>.json`: fetch status plus stdout and stderr tails.
- `GET /result/<job_id>.zip`: download the result zip.
- `GET /stdout/<job_id>.txt`: download full stdout, or use offsets.
- `GET /stderr/<job_id>.txt`: download full stderr, or use offsets.
- `POST /cancel/<job_id>`: request cancellation.
- `DELETE /job/<job_id>`: delete a job and its artefacts.
- `POST /purge`: purge matching jobs.

The full route contract is in [`api/openapi.json`](api/openapi.json).

## Pythonista client examples

Pythonista includes the `requests` module and a `dialogs` module for picking files.

### Example 1: submit a zip file you already built

```python
import requests

RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"
REQUEST_TIMEOUT_SECONDS = 60

with open("job.zip", "rb") as f:
    response = requests.post(
        RUNNER_URL + "/run",
        data=f,
        headers={
            "X-Runner-Token": TOKEN,
            "Content-Type": "application/zip",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

response.raise_for_status()
print(response.json())
```

### Example 2: use the reusable client helper

See [`app/pythonista_client.py`](app/pythonista_client.py) and [`examples/pythonista_run_job.py`](examples/pythonista_run_job.py).

## Troubleshooting

### `401 unauthorised`

Check all three of these:

1. **Access token** is set in the add-on configuration.
2. The request sends the correct `X-Runner-Token`.
3. **Ingress only** is off when you are calling the direct API.

### Pythonista cannot connect

Check that:

- The add-on is started.
- Your iPhone can reach the Home Assistant host on the local network.
- Port `8787` is not blocked by local firewall rules.
- Any CIDR allowlist includes your current client IP range.

### Upload fails immediately

Your zip must contain `run.py` at the zip root, not inside an extra parent folder.

### Result zip is missing your files

Only files written under `outputs/` are copied into the result zip.

### The Web UI loads but seems broken on mobile

Confirm you are on the latest add-on version, then hard refresh the Ingress page or restart the add-on so Home Assistant serves the current bundled `webui.html`.

## Security and operating notes

- Jobs run inside the add-on container, not on your iPhone.
- Direct API access and Ingress access are separate trust paths.
- Prefer Ingress for day-to-day human use.
- Keep direct API exposure local and token-protected.
- Review [`config.yaml`](config.yaml) before changing bind or security options.

## Packaging and architecture notes

The add-on declares support for `amd64`, `aarch64`, and `armv7` in [`config.yaml`](config.yaml), with matching build-matrix entries in [`build.yaml`](build.yaml).

Repository truthfulness note: automated runtime tests in this repository currently run on `amd64` continuous integration runners. `aarch64` and `armv7` are validated here at packaging and declaration level and still need native-host smoke testing before release sign-off.

## Advanced and contributor notes

- Repository landing page: [`../README.md`](../README.md)
- Security guidance: [`../SECURITY.md`](../SECURITY.md)
- Release channels: [`../docs/RELEASE_CHANNELS.md`](../docs/RELEASE_CHANNELS.md)
- Contributor guide: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- Web UI bundler: [`app/webui_build.py`](app/webui_build.py)
