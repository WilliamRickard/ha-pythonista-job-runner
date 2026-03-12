Version: 1.1.0
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
- `design-auditor`
- `home-assistant-addon-ui-modernisation`

Upstream sources:

- `home-assistant-best-practices`: `homeassistant-ai/skills`
- `web-design-guidelines`: `vercel-labs/agent-skills`
- `frontend-design-principles`: `joshuadavidthomas/agent-skills`
- `audit-ui`, `audit-typography`, `ui-animation`: `mblode/agent-skills`
- `a11y-audit`: `snapsynapse/skill-a11y-audit`
- `webapp-testing`: `anthropics/skills`
- `design-system-starter`: `ArieGoldkin/ai-agent-hub`
- `figma`: `openai/skills` (curated)
- `design-auditor`: repo-local distilled adaptation of the published `Ashutos1997/claude-design-auditor-skill` rubric
- `home-assistant-addon-ui-modernisation`: repo-local skill for this add-on UI and screenshot-backed planning workflow

Vendoring notes:

- Existing vendored skills remain as previously added.
- `design-auditor` is included as a repo-local skill so Codex can use a consistent 17-category audit rubric directly from the repo.
- `home-assistant-addon-ui-modernisation` is included to steer Codex toward a tracked plan, mobile-first operational clarity, and the highest-value files in this repo.
- Screenshot evidence for UI work now lives under `docs/ui_audit_screens/` so Codex cloud can inspect the design evidence from the repo itself.
