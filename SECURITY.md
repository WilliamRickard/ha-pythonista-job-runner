<!-- Version: 0.6.12-docs.10 -->
# Security policy

## Reporting a vulnerability

Do not open a public issue for a security-sensitive report.

If you believe you have found a security issue:

1. Check [`repository.yaml`](repository.yaml) for the maintainer contact.
2. Send a private report with:
   - a clear description of the issue
   - steps to reproduce
   - impact assessment
   - any proof-of-concept details you can share safely

## Safe default operating model

The safest normal setup is:

- set a strong, random **Access token**
- keep port `8787` on your local network only
- use **Allowed client CIDRs** if you know the client network range
- use Home Assistant Ingress for day-to-day browsing and downloads
- only turn on **Ingress only** when you intentionally want to block direct API access

Do not expose the direct API to the public internet.

## Access paths and trust boundaries

This add-on has two different access paths.

### Ingress Web UI

Home Assistant Ingress is authenticated by Home Assistant itself.

- It does not use `X-Runner-Token`.
- It is intended for people using the built-in Web UI from the Home Assistant session.
- This add-on keeps the bundled Web UI path-prefix-safe for Ingress.

### Direct API

The direct API listens on port `8787` by default.

- `GET /health` is intentionally unauthenticated.
- Other direct API routes require the configured `X-Runner-Token` unless the request is coming through Ingress.
- If the Access token is blank, direct non-Ingress access is denied.
- If `api_allow_cidrs` is configured, direct non-Ingress access must satisfy both checks: valid token and client IP inside the configured range.
- If `ingress_strict` is enabled, direct access is denied even when token and CIDR checks would otherwise pass.

In practice, direct API access only works when all of the following are true:

- the request is not just a simple `GET /health` probe
- `ingress_strict` is off
- the Access token is set and matches `X-Runner-Token`
- the client IP matches `api_allow_cidrs`, when a CIDR allowlist is configured

## Execution notes

- Jobs run inside the add-on container, not on your iPhone.
- The configured execution user is `runner.job_user` in [`pythonista_job_runner/config.yaml`](pythonista_job_runner/config.yaml), which defaults to `jobrunner`.
- If that user cannot be resolved and the container is running as root, the runner logs a warning because jobs would then run as root inside the container.

## Practical hardening checklist

- Review [`pythonista_job_runner/config.yaml`](pythonista_job_runner/config.yaml) before changing bind or security settings.
- Keep Home Assistant and installed add-ons up to date.
- Do not commit real tokens into example code, screenshots, or issue reports.
- Check screenshots for hostnames, usernames, repository URLs, IP addresses, and file paths before publishing them.

## Read next

- [`README.md`](README.md) for the fast project overview.
- [`pythonista_job_runner/README.md`](pythonista_job_runner/README.md) for the short add-on summary.
- [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md) for setup, API usage, and troubleshooting.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) for contributor workflow.
