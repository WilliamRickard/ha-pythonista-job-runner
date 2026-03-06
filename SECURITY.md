<!-- Version: 0.6.12-docs.3 -->
# Security policy

## Reporting a vulnerability

Please do not open public issues for security-sensitive reports.

If you believe you have found a security issue:

1. Check [`repository.yaml`](repository.yaml) for the maintainer contact.
2. Send a private report with:
   - A clear description of the issue
   - Steps to reproduce
   - Impact assessment
   - Any proof-of-concept details you can share safely

## Security model

This add-on runs arbitrary Python code that you upload. Treat it like running a script on your Home Assistant host.

Current authentication and access behaviour:

- The direct HTTP API listens on port `8787` by default.
- `GET /health` is intentionally unauthenticated.
- Home Assistant Ingress requests are trusted when they come from the Supervisor proxy IP. Ingress access does not use the runner token.
- Direct non-Ingress access requires the `X-Runner-Token` header to match the configured Access token.
- If the Access token is blank, direct non-Ingress API access is denied.
- If `api_allow_cidrs` is configured, direct non-Ingress access must satisfy both checks: valid token and client IP inside one of the configured CIDR ranges.
- If `ingress_strict` is enabled, only Ingress traffic is accepted. Direct access is denied even if the token and CIDR checks would otherwise pass.

In practice, direct API access works only when all of the following are true:

- You are not using the dedicated unauthenticated `GET /health` endpoint.
- The request is not being blocked by `ingress_strict`.
- The Access token is set and matches `X-Runner-Token`.
- The client IP matches `api_allow_cidrs`, if you configured one.

## Operating this add-on safely

Recommended practices:

- Set a strong, random Access token and keep it private.
- Prefer Home Assistant Ingress for day-to-day use.
- Do not expose port `8787` directly to the public internet.
- If you need remote access, prefer a VPN or Home Assistant Cloud rather than a public port forward.
- Use `api_allow_cidrs` to restrict direct API access to trusted networks.
- Only enable `ingress_strict` if you deliberately want to disable direct API access.
- Review [`pythonista_job_runner/config.yaml`](pythonista_job_runner/config.yaml) before changing bind or security settings.
- Keep Home Assistant and add-ons updated.

## Execution and privilege notes

- Jobs run inside the add-on container, not on your iPhone.
- The configured execution user is `runner.job_user` in [`pythonista_job_runner/config.yaml`](pythonista_job_runner/config.yaml), which defaults to `jobrunner`.
- If that user cannot be resolved and the container is running as root, the runner logs a warning because jobs would then run as root inside the container.

## Ingress notes

- Home Assistant Ingress is authenticated by Home Assistant itself.
- This add-on keeps the Ingress UI path-prefix-safe by serving a bundled Web UI and avoiding root-relative asset paths.
- Direct API access and Ingress access are separate paths with different authentication behaviour.

Further reading:

- [`README.md`](README.md) for the quick-start overview
- [`pythonista_job_runner/DOCS.md`](pythonista_job_runner/DOCS.md) for configuration, API usage, and troubleshooting
- [`CONTRIBUTING.md`](CONTRIBUTING.md) for contributor workflow and Web UI build guidance
