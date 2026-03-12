Version: 1.0.0
# Codex prompt for UI modernisation

Use the repo-local skills in `.agents/skills` and the repo guidance in `AGENTS.md`.

Important:
- Do not ask for confirmation.
- Do not stop after the audit.
- Do not stop after the plan.
- Create a tracked 27-step plan first, then implement steps 1 to 5 in the same run.
- Keep the current stack. Do not do a framework rewrite.
- Prioritise mobile-first operational clarity for a Home Assistant add-on UI.
- Use the screenshots already in the repo as design evidence, not just the code.

First, inspect:
- the repo
- `.agents/skills`
- `AGENTS.md`
- `docs/ui_audit_screens/`
- the repo-local `design-auditor` skill
- the repo-local `home-assistant-addon-ui-modernisation` skill

Then choose the 3 to 6 most relevant skills for this task and explain briefly why each applies.

After that, create a tracked plan file in the repo called:
`docs/ui_modernisation_plan.md`

Plan requirements:
- exactly 27 numbered steps
- one step for each of the 27 required improvement items listed below
- each step must have:
  - ID
  - title
  - rationale
  - target screens/components
  - likely files to change
  - tests to add or update
  - status: TODO / IN_PROGRESS / DONE / BLOCKED
  - notes
- order the plan for highest leverage first, but preserve all 27 items
- after creating the plan, immediately execute steps 1 to 5
- while working, update the plan statuses in the file
- when done, mark steps 1 to 5 as DONE or BLOCKED with notes
- leave steps 6 to 27 as TODO unless partially completed as dependencies

The 27 required plan items are:

1. Reduce the top-heavy mobile hierarchy so the main operational surface starts higher on screen.
2. Reorganise the log controls so they are grouped, easier to scan, and no longer feel like an undifferentiated toolbox.
3. Hide setup implementation detail behind a more guided flow so users do not have to understand the system model too early.
4. Remove or resolve header duplication so the top of the mobile UI is not visually heavy.
5. Make filters significantly more compact and intuitive on narrow screens.
6. Strengthen status semantics with shape, iconography, and hierarchy, not just color.
7. Sharpen microcopy so it tells the user what to do next rather than only explaining what the screen is.
8. Add progressive disclosure to setup and advanced surfaces so low-frequency detail is not always expanded.
9. Make the UI feel more Home Assistant-native and less like a bespoke admin panel.
10. Reduce how early job rows force users to parse machine detail such as IDs and technical metadata.
11. Systematise action placement across screens so the location and role of actions are consistent.
12. Improve empty and low-data states so they guide action rather than sitting as flat placeholders.
13. Make segmented content in detail views more distinct so view modes feel like deliberate sections, not weak pills.
14. Strengthen the hierarchy between routine information and advanced diagnostic information.
15. Introduce stronger visual rhythm at section boundaries so screens scan faster and feel less monotonous.
16. Redesign jobs list rows around human recognition first, not raw metadata first.
17. Standardise action architecture across the app, including global, section, inline, and overflow actions.
18. Introduce a stronger collapsed-by-default pattern for technical depth and advanced diagnostics.
19. Add a true triage layer so the UI immediately surfaces what needs attention now.
20. Make time information decision-friendly so users can quickly tell what is recent, stale, active, or long-running.
21. Make success and completion states clearer so healthy states feel resolved rather than merely “not failing”.
22. Differentiate harmless, state-changing, destructive, and diagnostic actions so controls do not all feel equally reversible.
23. Add stronger “where am I?” cues so users always understand host, job, mode, view, and scope.
24. Make content density elastic so lists, forms, configuration, and reading surfaces are not all equally dense.
25. Layer inline help so first-level screens stay light, with deeper explanation available progressively.
26. Create a stronger primary path through each major screen so recommended actions are obvious.
27. Improve the transition logic between overview and detail so moving deeper feels coherent and contextual.

Execution requirements after the plan is created:
- implement steps 1 to 5 immediately
- do not just describe them
- make the code changes directly in the repo
- update the plan file as you go
- keep changes tightly scoped to the first 5 steps, except for small dependencies
- if a dependency from a later step is required, do the smallest safe version and note it in the plan

Audit requirements before editing:
Use the design-auditor rubric and evaluate the current UI against:
- visual hierarchy
- spacing and layout
- typography
- state communication
- iconography
- navigation
- action hierarchy
- responsive/mobile behaviour
- setup and progressive disclosure
- accessibility
- Home Assistant fit
- content density
- empty/loading/error states
- overview-to-detail continuity

Testing requirements:
After implementing steps 1 to 5:
- run the relevant build and tests
- add or update regression tests for the first 5 plan steps where practical
- include interaction-focused tests, not only copy-based tests
- cover mobile layout where relevant
- cover focus and reduced-motion behaviour where relevant
- cover filter behaviour and top-of-screen hierarchy where practical

Evidence requirements:
At the end, provide:
1. the selected skills and how each influenced the work
2. the audit summary
3. the 27-step tracked plan summary
4. exact files changed
5. tests run and results
6. before/after screenshots for the screens affected by steps 1 to 5
7. what remains for steps 6 to 27
