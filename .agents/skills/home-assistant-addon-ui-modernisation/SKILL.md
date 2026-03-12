---
name: home-assistant-addon-ui-modernisation
description: Use this skill when improving the Pythonista Job Runner Home Assistant add-on web UI for modern look and feel, mobile-first usability, operational clarity, and consistent action hierarchy without rewriting the current HTML/CSS/JS stack.
version: 1.0.0
---

# Home Assistant Add-on UI Modernisation

Use this skill for targeted UI modernisation work in this repo.

## Repo-specific evidence
Always inspect:
- `docs/ui_audit_screens/`
- `pythonista_job_runner/app/webui_html/`
- `pythonista_job_runner/app/webui_css/`
- relevant UI tests under `pythonista_job_runner/tests/`

## Primary goals
- modernise the UI without a framework rewrite
- improve mobile-first hierarchy and scanability
- reduce control clutter
- make states and next actions clearer
- align the UI more closely with Home Assistant expectations

## Required workflow
1. Audit first.
2. Create a tracked plan in `docs/ui_modernisation_plan.md`.
3. Tie each plan item to files and tests.
4. Implement the highest-leverage steps first.
5. Update the plan while working.
6. Add or update regression tests.
7. Provide before and after screenshots for affected screens when possible.

## Priority lenses
- operational clarity beats decoration
- compact mobile hierarchy beats large hero chrome
- consistent action placement beats ad hoc button rows
- progressive disclosure beats always-expanded technical detail
- semantic state treatment beats color-only signalling

## High-value target areas in this repo
- `pythonista_job_runner/app/webui_html/00_shell.html`
- `pythonista_job_runner/app/webui_html/20_jobs.html`
- `pythonista_job_runner/app/webui_html/30_detail.html`
- `pythonista_job_runner/app/webui_html/42_setup.html`
- `pythonista_job_runner/app/webui_css/10_layout.css`
- `pythonista_job_runner/app/webui_css/20_jobs_table.css`
- `pythonista_job_runner/app/webui_css/50_responsive.css`

## Plan quality bar
A good plan should include:
- rationale
- screen or component scope
- likely files
- test changes
- tracked status
- implementation notes

## Default success criteria
- cleaner top-of-screen mobile layout
- clearer jobs-first operational scanning
- more compact and intuitive filters
- more structured log controls
- setup and advanced areas with stronger progressive disclosure
- stronger state communication and action hierarchy
