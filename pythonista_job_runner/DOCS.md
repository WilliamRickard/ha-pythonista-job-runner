<!-- Version: 0.6.12-docs.9 -->
# Pythonista Job Runner

Pythonista Job Runner is a Home Assistant add-on that:

1. Accepts a job zip uploaded from Pythonista (iOS).
2. Extracts it into an isolated working directory.
3. Runs `run.py`.
4. Streams logs (stdout and stderr) while it runs.
5. Builds a result zip you can download back to the phone.

It also includes a Home Assistant Ingress Web UI for viewing jobs, logs, and downloading results from inside Home Assistant.

## Who this is for

This add-on is useful when you want your iPhone to be the control surface (Pythonista UI, shortcuts, on-device scripts), but you want the actual work to run somewhere more capable:

- CPU-intensive tasks that are slow on iOS
- Work that needs Linux tooling (git, compilers, system packages)
- Jobs that need packages that are awkward on iOS
- Running long tasks without keeping the phone awake

## Install and first run

### 1) Add the repository

If you have not added this GitHub repository to Home Assistant yet, add it via:

- Settings -> Add-ons -> Add-on Store -> menu -> Repositories
- Add: `https://github.com/WilliamRickard/ha-pythonista-job-runner`

Home Assistant also supports a "My Home Assistant" link that opens the repository dialog pre-filled. See the [repository root README](../README.md).

Home Assistant documentation (developer docs):
- https://developers.home-assistant.io/docs/apps/repository/

### 2) Install the add-on

1. Find **Pythonista Job Runner** in the add-on store.
2. Install it.
3. Start it.

### 3) Configure security (do this before using the HTTP API)

In the add-on Configuration tab:

- Security -> Access token
  - Direct API clients such as Pythonista must send this value in the `X-Runner-Token` header.
  - If this value is blank, direct API access is disabled.
- Security -> Ingress only
  - This is the `ingress_strict` option in the add-on config.
  - If enabled, only Home Assistant Ingress can access the add-on.
  - This is great for the Web UI, but it blocks direct calls from Pythonista.
- Security -> Allowed client CIDRs
  - This is the `api_allow_cidrs` option in the add-on config.
  - If set, direct API requests must come from an allowed network as well as present the correct token.

Typical setup for Pythonista usage:

- Set a strong Access token.
- Leave "Ingress only" OFF so Pythonista can connect directly.
- Optionally set "Allowed client CIDRs" to your local network range (for example, your Wi-Fi subnet) so the API is not reachable from everywhere.

Remote access tip: do not expose the add-on port directly to the internet. If you need remote access, prefer a VPN or Home Assistant Cloud, and keep your Home Assistant instance secured.

## How to reach the API

The add-on exposes its HTTP API on port 8787 (by default). The base URL will look like one of these:

- `http://YOUR_HOME_ASSISTANT_HOST:8787`
- `http://YOUR_HOME_ASSISTANT_IP:8787`

Ingress Web UI (inside Home Assistant):
- Open the add-on and click **Open Web UI**.
- Ingress is authenticated by Home Assistant. Home Assistant recommends add-ons restrict Ingress traffic to the Supervisor proxy IP `172.30.32.2` and deny others. This add-on treats Ingress traffic as trusted. Home Assistant Ingress requirements are documented here:
  - https://developers.home-assistant.io/docs/apps/presentation/#ingress

## Ingress versus direct API access

Use **Ingress** when you are interacting with the built-in Web UI from inside Home Assistant. Use the **direct API** when Pythonista or another script is uploading jobs over the network.

### Ingress

Ingress is the simplest path for humans using the Web UI:

1. Open the add-on inside Home Assistant.
2. Click **Open Web UI**.
3. Browse jobs, logs, and result downloads in the authenticated Home Assistant session.

Ingress requests are authenticated by Home Assistant itself and proxied to the add-on. You do not send `X-Runner-Token` manually in this flow. `GET /health` is separate and intentionally unauthenticated for simple connectivity checks.

### Direct API

The direct API is the path Pythonista uses. This goes to port `8787` on your Home Assistant host and requires `X-Runner-Token`. It only works when an Access token is set, `ingress_strict` is off, and your client IP matches any configured `api_allow_cidrs`.

Concrete Pythonista example:

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

Rule of thumb:

- Open Web UI inside Home Assistant: use Ingress.
- Upload from Pythonista on your phone: use the direct API with `X-Runner-Token`.

## Job zip format

Your upload must be a zip file that contains `run.py` at the root.

- `run.py` is executed as the job entry point.
- Any other files in the zip are extracted into the job working directory.
- If your code writes files under `outputs/`, they are included in the result zip.

Example `run.py` that produces an output file:

```python
import os
from datetime import datetime

print("Job started")

os.makedirs("outputs", exist_ok=True)
with open("outputs/when.txt", "w", encoding="utf-8") as f:
    f.write(datetime.utcnow().isoformat() + "Z\n")

print("Job finished")
```

### Optional: `requirements.txt`

The add-on can optionally install dependencies listed in `requirements.txt` (at the job root) into a per-job directory.

This is OFF by default. To use it:

1. In add-on Configuration -> Python -> Install requirements: set to true.
2. Include a `requirements.txt` file in the job zip root.

Security note: installing requirements may execute build hooks. Only enable this if you trust the job code you are running.

## Result zip format

When the job completes (success or failure), the result zip includes:

- `stdout.txt` and `stderr.txt`
- `status.json` (the final job status)
- `exit_code.txt`
- `summary.txt` (includes tail excerpts)
- `result_manifest.json`
- `job.log` (metadata about the run)
- Optional: `pip_install_stdout.txt`, `pip_install_stderr.txt` (only if requirements installation was used)
- Your files under `outputs/` (if any)

## HTTP API reference

All endpoints are served by the add-on.

### Public endpoints (no token required)

- `GET /health`  
  Returns `{"status": "ok", "version": "<addon version>"}`.

- `GET /` or `GET /index.html`  
  Returns JSON info by default. If the client sends an `Accept` header that prefers HTML (for example a browser), it returns the Web UI and requires authentication.

- `GET /info.json`  
  Returns the same JSON info as `/`.

### Authenticated endpoints (token required unless coming through Ingress)

Send the token in this header:

- `X-Runner-Token: <access token>`

Endpoints:

- `POST /run`  
  Submit a job zip as raw bytes in the request body. Response is HTTP 202 with JSON:

  ```json
  {
    "job_id": "…",
    "tail_url": "/tail/<job_id>.json",
    "result_url": "/result/<job_id>.zip",
    "jobs_url": "/jobs.json"
  }
  ```

- `GET /jobs.json`  
  List jobs.

- `GET /job/<job_id>.json`  
  Job status.

- `GET /tail/<job_id>.json`  
  Job status plus tail logs (stdout and stderr).

  You can optionally use offsets for incremental fetching:

  - `stdout_from=<int>`
  - `stderr_from=<int>`
  - `max_bytes=<int>` (capped to 1 MiB per stream)

- `GET /result/<job_id>.zip`  
  Download the result zip.

- `GET /stdout/<job_id>.txt` and `GET /stderr/<job_id>.txt`  
  Download full logs, or use deltas with query parameters:

  - `from=<int>`
  - `max_bytes=<int>` (capped)

- `POST /cancel/<job_id>`  
  Request cancellation.

- `DELETE /job/<job_id>`  
  Delete a job and its artefacts.

- `POST /purge`  
  Purge multiple jobs. Body is JSON, for example:

  ```json
  {
    "states": ["done", "error"],
    "older_than_hours": 24,
    "dry_run": true
  }
  ```

## Pythonista client examples

Pythonista includes the `requests` module and a `dialogs` module for a file picker:

- Requests docs (Pythonista): https://omz-software.com/pythonista/docs/ios/requests.html
- dialogs.pick_document docs: https://omz-software.com/pythonista/docs/ios/dialogs.html#importing-files

### Example 1: Build a zip in Pythonista and run it

This script:

- Builds a job zip in a temporary directory
- Uploads it to Home Assistant
- Polls the tail endpoint until the job is finished
- Downloads and extracts the result zip

```python
"""Pythonista client for Pythonista Job Runner.

Edit RUNNER_URL and TOKEN, then run in Pythonista. The placeholder host name and token below match the shorter examples elsewhere in this guide.
"""

import io
import json
import os
import tempfile
import time
import zipfile

import requests


RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"
SUBMIT_TIMEOUT_SECONDS = 60


def build_job_zip(zip_path):
    """Create a minimal job zip with run.py at the zip root."""
    run_py = """import os

print("Hello from Home Assistant")
os.makedirs("outputs", exist_ok=True)
with open("outputs/hello.txt", "w", encoding="utf-8") as f:
    f.write("Created by the add-on.\n")
"""
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("run.py", run_py)


def submit_job(zip_path):
    """Upload the zip and return the parsed JSON response."""
    with open(zip_path, "rb") as f:
        r = requests.post(
            RUNNER_URL + "/run",
            data=f,  # raw zip bytes
            headers={"X-Runner-Token": TOKEN},
            timeout=SUBMIT_TIMEOUT_SECONDS,
        )
    r.raise_for_status()
    return r.json()


def poll_until_done(job_id, poll_seconds=1):
    """Poll /tail until the job state is done or error."""
    last_out = 0
    last_err = 0
    while True:
        r = requests.get(
            RUNNER_URL + "/tail/{}.json".format(job_id),
            params={"stdout_from": last_out, "stderr_from": last_err},
            headers={"X-Runner-Token": TOKEN},
            timeout=POLL_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        payload = r.json()

        status = payload.get("status") or {}
        tail = payload.get("tail") or {}
        offsets = payload.get("offsets") or {}

        out = tail.get("stdout") or ""
        err = tail.get("stderr") or ""
        if out:
            print(out, end="")
        if err:
            print(err, end="")

        last_out = int(offsets.get("stdout_next", last_out))
        last_err = int(offsets.get("stderr_next", last_err))

        state = status.get("state")
        if state in ("done", "error"):
            return status

        time.sleep(poll_seconds)


def download_result(job_id, out_zip_path):
    """Download /result/<job_id>.zip."""
    r = requests.get(
        RUNNER_URL + "/result/{}.zip".format(job_id),
        headers={"X-Runner-Token": TOKEN},
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    with open(out_zip_path, "wb") as f:
        f.write(r.content)


def main():
    tmp = tempfile.mkdtemp(prefix="runner_job_")
    job_zip = os.path.join(tmp, "job.zip")
    result_zip = os.path.join(tmp, "result.zip")
    result_dir = os.path.join(tmp, "result")

    build_job_zip(job_zip)
    resp = submit_job(job_zip)
    job_id = resp["job_id"]
    print("Submitted job:", job_id)

    status = poll_until_done(job_id)
    print("\nFinal status:", json.dumps(status, indent=2))

    download_result(job_id, result_zip)
    os.makedirs(result_dir, exist_ok=True)
    with zipfile.ZipFile(result_zip, "r") as zf:
        zf.extractall(result_dir)

    print("Result extracted to:", result_dir)
    print("Files:", os.listdir(result_dir))


if __name__ == "__main__":
    main()
```

### Example 2: Upload an existing zip using a file picker

If you already have a `job.zip` saved in Files, you can pick it:

```python
"""Pick an existing job zip from Files and upload it."""

import requests
import dialogs

RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"
SUBMIT_TIMEOUT_SECONDS = 60


def main():
    path = dialogs.pick_document()  # returns a temporary file path
    if not path:
        print("No file picked")
        return

    with open(path, "rb") as f:
        r = requests.post(
            RUNNER_URL + "/run",
            data=f,
            headers={"X-Runner-Token": TOKEN},
            timeout=SUBMIT_TIMEOUT_SECONDS,
        )

    r.raise_for_status()
    print(r.json())


if __name__ == "__main__":
    main()
```

Note: `dialogs.pick_document()` returns a temporary file path. If you need to keep the selected file, move or copy it into your Pythonista Documents folder.

## Troubleshooting

### 401 unauthorised

Causes:

- Missing or wrong `X-Runner-Token`.
- Access token is blank, so direct API access is disabled.
- "Ingress only" (`ingress_strict`) is enabled, and you are calling the API directly from Pythonista.
- You set "Allowed client CIDRs" (`api_allow_cidrs`) and your phone is not in the allowed range.

Fix:

- Confirm the token matches the configured Access token.
- Set an Access token if you want direct Pythonista access.
- Disable "Ingress only" if you need direct Pythonista access.
- Adjust the CIDR allowlist.

### Cannot connect

- Confirm the add-on is running.
- Confirm you can reach `http://YOUR_HOME_ASSISTANT_HOST:8787/health` from the same network.
- If you are using HTTPS for Home Assistant, note the add-on port is still HTTP by default. Use a VPN, a reverse proxy, or keep it local.

### 413 upload too large

- The add-on enforces upload and zip safety limits. Reduce your job zip size or increase limits in the add-on configuration if you understand the trade-offs.

### Job times out

- Increase Jobs -> Timeout seconds.
- Reduce work per job or split into multiple jobs.

## Developer notes

- [`README.md`](README.md) is the short entry.
- [`DOCS.md`](DOCS.md) is the full user documentation shown in the add-on UI.
- [`CHANGELOG.md`](CHANGELOG.md) tracks add-on changes.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) covers contributor workflow, Web UI build rules, and local checks.

## Advanced: Web UI customisation

This section is for contributors who want to change the built-in Web UI. For normal usage, you do not need this.

The add-on serves the Web UI as a single Ingress-safe file ([`app/webui.html`](app/webui.html)). Do not edit that file directly. It is generated.

Edit these source files instead:

- [`app/webui_src.html`](app/webui_src.html) (HTML wrapper and placeholders)
- [`app/webui_html/`](app/webui_html/) (`*.html`, HTML body partials)
- [`app/webui_css/`](app/webui_css/) (`*.css`, CSS parts)
- [`app/webui_js/`](app/webui_js/) (`*.js`, JavaScript parts)

Rebuild generated outputs:

- `python pythonista_job_runner/app/webui_build.py`

Check that generated outputs are up to date:

- `python pythonista_job_runner/app/webui_build.py --check`

Generated outputs (do not edit by hand):

- [`app/webui.html`](app/webui.html)
- [`app/webui.css`](app/webui.css)
- [`app/webui.js`](app/webui.js)

Build rules enforced by [`app/webui_build.py`](app/webui_build.py):

- Deterministic part ordering: the builder enforces explicit ordered lists for HTML, CSS, and JS parts.
- No root-relative URLs: references like `href="/..."`, `fetch("/...")`, or `url(/...)` are rejected because Home Assistant Ingress runs under a path prefix.
- HTML ids must be unique across all partials.
- JS parts must not declare their own `VERSION:` headers; the generated `webui.js` header is the single source of truth.

After rebuilding, run the test suite:

- `pytest -q` (from the `pythonista_job_runner/` folder)

For the contributor-focused version of this workflow, see [../CONTRIBUTING.md](../CONTRIBUTING.md#web-ui-build).
