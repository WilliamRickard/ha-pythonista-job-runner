<!-- Version: 0.6.12-docs.1 -->
# Security policy

## Reporting a vulnerability

Please do not open public issues for security-sensitive reports.

If you believe you have found a security issue:

1. Check `repository.yaml` for the maintainer contact.
2. Send a private report with:
   - A clear description of the issue
   - Steps to reproduce
   - Impact assessment
   - Any proof-of-concept details you can share safely

## Operating this add-on safely

This add-on runs arbitrary Python code that you upload. Treat it like running a script on your Home Assistant machine.

Recommended practices:

- Set a strong, random Access token and keep it private.
- Prefer keeping the API reachable only on your home network.
- Do not expose the add-on port directly to the internet.
- If you need remote access, prefer a VPN or Home Assistant Cloud.
- Consider using "Allowed client CIDRs" to restrict direct access.
- Keep Home Assistant and add-ons updated.

Ingress notes:

- Home Assistant Ingress is authenticated by Home Assistant itself.
- Home Assistant recommends add-ons restrict Ingress traffic to the Supervisor proxy IP and deny others.
- This add-on treats Ingress traffic as trusted and requires a token for direct (non-Ingress) access.

See Home Assistant developer docs on Ingress:
- https://developers.home-assistant.io/docs/apps/presentation/#ingress
