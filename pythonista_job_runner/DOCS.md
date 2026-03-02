# Pythonista Job Runner

Pythonista Job Runner is a Home Assistant add-on that accepts a job zip from Pythonista (iOS), runs `run.py`, and returns a result zip. It includes an Ingress Web UI for viewing job status and logs.

## What you get

- A simple HTTP API: submit job, stream logs, download results.
- A Web UI (Ingress) for viewing jobs and logs without leaving Home Assistant.
- Defensive defaults: size limits, zip-bomb protection, retention and cleanup.

## Quick start

1. Install the add-on and start it.
2. Open **Configuration** and set a strong **Access token**.
3. Open **Open Web UI** to confirm the UI loads.
4. From Pythonista, `POST` your job zip to `/run` with header `X-Runner-Token: <token>`.

## Job zip format

Your upload must be a zip file that contains `run.py` at the root.

- `run.py` is executed as the job entry point.
- Any other files in the zip are extracted into the job working directory.

## HTTP API

All endpoints are served by the add-on.

- `GET /`  
  Web UI.

- `GET /health`  
  Health check.

- `POST /run`  
  Submit a job zip. Requires `X-Runner-Token`.

- `GET /jobs.json`  
  Job list.

- `GET /status/<job_id>.json`  
  Job status.

- `GET /tail/<job_id>.json?stdout_offset=<n>&stderr_offset=<n>`  
  Incremental stdout/stderr tail.

- `GET /result/<job_id>.zip`  
  Download results for a completed job.

## Configuration (what most people change)

In the Home Assistant add-on UI, settings are grouped and include inline descriptions.

Most users only need:

- **Security → Access token** (required)

Optional but common:

- **Security → Ingress only** (recommended)
- **Notifications → Notify on completion**

Everything else is tuning. If you are not sure, leave the defaults.

## Security model

- The add-on requires a token header (`X-Runner-Token`) for non-Ingress requests.
- When using Home Assistant Ingress, Home Assistant provides user metadata headers and the add-on can lock down requests to the Ingress proxy IP.
- Uploaded zip handling is hardened with member count and size limits.

## Troubleshooting

- Web UI loads but submissions fail: confirm Pythonista is sending `X-Runner-Token` and you set the token in the add-on config.
- Jobs fail immediately with `zip_missing_run_py`: your zip must contain `run.py` at the root.
- Disk space issues: reduce retention or enable housekeeping cleanup.

## Editing the Web UI

The add-on serves a single `webui.html` file so it works reliably behind Home Assistant Ingress.

To make edits easier, the UI source is split into:

- `pythonista_job_runner/app/webui_src.html`
- `pythonista_job_runner/app/webui.css`
- `pythonista_job_runner/app/webui.js`

After editing, regenerate `webui.html` by running from the repository root:

    python pythonista_job_runner/app/webui_build.py

The test suite includes a check to ensure `webui.html` is up-to-date with the source files.
