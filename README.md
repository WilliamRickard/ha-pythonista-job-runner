<!-- Version: 0.6.12-docs.1 -->
# Pythonista Job Runner add-on repository

This repository contains a Home Assistant add-on that lets Pythonista (iOS) send a zipped Python job to Home Assistant, run it on the Home Assistant machine, and download the results as a zip.

If you only want to use the add-on, start here and then read the full add-on docs in `pythonista_job_runner/DOCS.md`.

## Install this repository in Home Assistant

Option A (recommended): My Home Assistant link

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FWilliamRickard%2Fha-pythonista-job-runner)

Option B: manual

1. In Home Assistant, go to Settings -> Add-ons -> Add-on Store.
2. Open the top-right menu (three dots) -> Repositories.
3. Add:
   `https://github.com/WilliamRickard/ha-pythonista-job-runner`

Home Assistant documentation (developer docs):
- https://developers.home-assistant.io/docs/apps/repository/

## Install and use the add-on

1. Open the add-on store entry for **Pythonista Job Runner** and install it.
2. Open the add-on configuration and set a strong **Access token**.
3. Start the add-on.
4. Open **Open Web UI** to confirm the Ingress UI loads.
5. From Pythonista, upload a job zip to:
   `http://<your-home-assistant-host>:8787/run`
   with HTTP header:
   `X-Runner-Token: <your token>`

For details, examples, and troubleshooting:
- `pythonista_job_runner/DOCS.md` (full user guide)
- `pythonista_job_runner/README.md` (short version)

## What the job zip looks like

Your upload is a zip file with `run.py` at the root. Anything else in the zip is unpacked next to it and is available to your script.

Minimal `run.py` example:

```python
import os

print("Hello from the Home Assistant add-on")

os.makedirs("outputs", exist_ok=True)
with open("outputs/hello.txt", "w", encoding="utf-8") as f:
    f.write("It worked.\n")
```

When the job completes, the add-on returns a result zip that always includes `stdout.txt`, `stderr.txt`, and `status.json`. If your script wrote files under `outputs/`, they are included too.

## Support

- For usage and troubleshooting, start with `pythonista_job_runner/DOCS.md`.
- For bugs and feature requests, open a GitHub issue in this repository.
