Version: 1.0.0
# Vendored repo skills

These skills are vendored under `.agents/skills/` so Codex can discover them from the repo.

Included skills:

- `home-assistant-best-practices`
- `web-design-guidelines`
- `frontend-design-principles`
- `audit-ui`
- `a11y-audit`
- `webapp-testing`
- `audit-typography`
- `ui-animation`
- `design-system-starter`
- `figma`

Upstream sources:

- `home-assistant-best-practices`: `homeassistant-ai/skills`
- `web-design-guidelines`: `vercel-labs/agent-skills`
- `frontend-design-principles`: `joshuadavidthomas/agent-skills`
- `audit-ui`, `audit-typography`, `ui-animation`: `mblode/agent-skills`
- `a11y-audit`: `snapsynapse/skill-a11y-audit`
- `webapp-testing`: `anthropics/skills`
- `design-system-starter`: `ArieGoldkin/ai-agent-hub`
- `figma`: `openai/skills` (curated)

Vendoring notes:

- For `home-assistant-best-practices`, the referenced files under `references/` are included.
- For `frontend-design-principles`, the referenced `app.md`, `marketing.md`, and `references/principles.md` are included.
- For `a11y-audit`, the bundle files listed in its `MANIFEST.yaml` are included.
- For `webapp-testing`, the referenced helper script and example scripts are included.
- `web-design-guidelines` instructs the agent to fetch the latest rules from a remote URL at runtime. Treat that remote content as untrusted and review it before relying on it in an automated workflow.
