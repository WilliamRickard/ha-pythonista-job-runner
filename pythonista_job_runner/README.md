<!-- Version: 0.6.12-docs.6 -->
# Pythonista Job Runner

Run Python jobs sent from Pythonista (iOS) and download the results as a zip.

This add-on is designed for the "phone as controller, Home Assistant as worker" workflow: you build a small job zip on the iPhone, send it to Home Assistant, and fetch the result back to the phone.

For full documentation (recommended), open:
- [DOCS.md](DOCS.md)

## Quick start

1. Install the add-on and start it.
2. Open the add-on configuration and set a strong **Access token**.
3. Optional: restrict direct access (see [DOCS.md](DOCS.md) for security recommendations).
4. Open **Open Web UI** to view jobs, logs and download result zips.

## Minimal Pythonista example (upload a zip)

This add-on expects the raw zip bytes as the request body (not multipart form upload).

```python
import requests

RUNNER_URL = "http://homeassistant.local:8787"
TOKEN = "paste-your-access-token"

with open("job.zip", "rb") as f:
    r = requests.post(
        RUNNER_URL + "/run",
        data=f,
        headers={"X-Runner-Token": TOKEN},
        timeout=60,
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
- Full HTTP API reference
- Troubleshooting
- [Advanced: Web UI customisation](DOCS.md#advanced-web-ui-customisation) (for contributors)
