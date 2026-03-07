<!-- Version: 0.6.12-docs.8 -->
# Pythonista Job Runner

Run Python jobs sent from Pythonista (iOS) and download the results as a zip.

This add-on is designed for the "phone as controller, Home Assistant as worker" workflow: you build a small job zip on the iPhone, send it to Home Assistant, and fetch the result back to the phone.

This file is the short add-on introduction. For the full guide, API reference, troubleshooting, and security detail, open [DOCS.md](DOCS.md).

## Quick start

## Architecture support

The add-on **declares** support for `amd64`, `aarch64`, and `armv7`, using Home Assistant base Python images configured in [`build.yaml`](build.yaml). CI verifies config/build alignment for these architecture declarations.

Truthfulness note: this repository's automated runtime tests currently run on `amd64` CI runners; `aarch64` and `armv7` are validated at packaging/declaration level here and still require native-host smoke testing before release sign-off.


1. Install the add-on and start it.
2. Open the add-on configuration and set a strong **Access token**.
3. Optional: restrict direct access (see [DOCS.md](DOCS.md) for security recommendations).
4. Open **Open Web UI** to view jobs, logs and download result zips.

## Minimal Pythonista example (upload a zip)

This add-on expects the raw zip bytes as the request body (not multipart form upload).

```python
import requests

RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"
REQUEST_TIMEOUT_SECONDS = 60

with open("job.zip", "rb") as f:
    r = requests.post(
        RUNNER_URL + "/run",
        data=f,
        headers={"X-Runner-Token": TOKEN},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

r.raise_for_status()
print(r.status_code, r.json())
```

The response contains `job_id` plus URLs such as `tail_url` and `result_url`.

## Documentation

See [DOCS.md](DOCS.md) for:

- Installation, configuration, and security notes
- Job zip format and result zip format
- Pythonista client scripts (including polling logs and downloading results)
- Machine-readable API contract ([`api/openapi.json`](api/openapi.json))
- Reusable Pythonista client toolkit ([`app/pythonista_client.py`](app/pythonista_client.py)) and runnable example ([`examples/pythonista_run_job.py`](examples/pythonista_run_job.py))
- Full HTTP API reference
- Troubleshooting
- [Ingress versus direct API access](DOCS.md#ingress-versus-direct-api-access)
- [Advanced: Web UI customisation](DOCS.md#advanced-web-ui-customisation) (for contributors)


## Platform hardening notes

- Add-on ingress now enables streamed uploads (`ingress_stream: true`) for safer large payload handling through Home Assistant ingress.
- A custom `apparmor.txt` profile is included and the add-on config explicitly declares non-privileged runtime flags.
- Job and control actions are written to `/data/audit_events.jsonl` with ingress identity metadata when Home Assistant provides `X-Remote-User-*` headers.
- Companion Home Assistant integration is available under `custom_components/pythonista_job_runner` with sensors, system health, and repair issue hooks.
