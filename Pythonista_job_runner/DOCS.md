# Pythonista Job Runner

Run Python jobs sent from Pythonista and return results as a zip.

## Quick start

1. Install and start the add-on.
2. Set a strong `token` in add-on configuration.
3. From Pythonista, POST your job zip to `/run` with header `X-Runner-Token`.
4. Poll `/tail/<job_id>.json` and download `/result/<job_id>.zip`.

## Web UI

The add-on uses Home Assistant Ingress, so you can open the Web UI from the add-on page.

## Configuration

See `config.yaml` for all options and defaults. Key ones:
- `token`: Required for direct API calls (non-Ingress).
- `ingress_strict`: If true, only Ingress proxy IP can access the server.
- `api_allow_cidrs`: Optional allowlist for direct API access.
- `default_cpu_percent`, `default_mem_mb`, `max_threads`: Resource limits.

## Security notes

- Do not expose the API directly to the internet.
- Prefer access via Ingress and/or Tailscale.
