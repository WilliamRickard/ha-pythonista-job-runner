# Pythonista Job Runner

Run Python jobs sent from Pythonista (iOS) and download the results as a zip.

You typically only need to set the **Access token** in the add-on configuration. Everything else has reasonable defaults.

## Quick start

1. Install the add-on and start it.
2. Open **Configuration** and set a strong **Access token**.
3. Open **Open Web UI** to view jobs, logs and download result zips.

## Sending a job from Pythonista

- Send a zip containing a `run.py` at the root.
- `POST /run` with header `X-Runner-Token: <token>`.
- Poll `GET /tail/<job_id>.json` while it runs.
- Download `GET /result/<job_id>.zip` when complete.

## Documentation

See **DOCS.md** in this add-on for full details, security notes and troubleshooting.
