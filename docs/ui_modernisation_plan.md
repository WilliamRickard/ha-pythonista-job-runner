# UI Modernisation Plan (Tracked)

Status legend: TODO / IN_PROGRESS / DONE / BLOCKED

1. **ID:** PJR-UI-01  
   **Title:** Lift the operational surface higher on mobile  
   **Rationale:** Screenshot evidence shows top chrome consuming too much first viewport before users reach active jobs.  
   **Target screens/components:** App header, jobs card top region (mobile).  
   **Likely files to change:** `pythonista_job_runner/app/webui_html/00_shell.html`, `pythonista_job_runner/app/webui_css/10_layout.css`, `pythonista_job_runner/app/webui_css/50_responsive.css`.  
   **Tests to add or update:** Mobile layout guardrail test for reduced top spacing and compact header.  
   **Status:** DONE  
   **Notes:** Completed by compacting header copy/actions and reducing top spacing so search and state controls appear earlier.

2. **ID:** PJR-UI-02  
   **Title:** Group log controls into clearer clusters  
   **Rationale:** Log controls currently read as one long toolbox; grouping improves scan speed and confidence under pressure.  
   **Target screens/components:** Detail log controls in job detail surface.  
   **Likely files to change:** `pythonista_job_runner/app/webui_html/30_detail.html`, `pythonista_job_runner/app/webui_css/20_jobs_table.css`, `pythonista_job_runner/app/webui_css/30_logs.css`.  
   **Tests to add or update:** Bundle test for log control groups and interaction-oriented controls presence.  
   **Status:** DONE  
   **Notes:** Completed via grouped sections for live/session controls, readability controls, highlights, and find.

3. **ID:** PJR-UI-03  
   **Title:** Introduce guided setup flow before implementation detail  
   **Rationale:** Users should start with readiness path first, not parse full system model immediately.  
   **Target screens/components:** Setup modal sections and defaults.  
   **Likely files to change:** `pythonista_job_runner/app/webui_html/42_setup.html`, `pythonista_job_runner/app/webui_css/40_overlays.css`.  
   **Tests to add or update:** Setup modal structure test (guided intro, collapsed advanced groups).  
   **Status:** DONE  
   **Notes:** Completed with a guided intro, step framing, and advanced sections collapsed by default.

4. **ID:** PJR-UI-04  
   **Title:** Resolve redundant top-header hierarchy  
   **Rationale:** Duplication between app title and jobs heading inflates visual weight on small screens.  
   **Target screens/components:** Global header + jobs header relationship.  
   **Likely files to change:** `pythonista_job_runner/app/webui_html/20_jobs.html`, `pythonista_job_runner/app/webui_css/10_layout.css`, `pythonista_job_runner/app/webui_css/50_responsive.css`.  
   **Tests to add or update:** Bundle test for compact jobs header variant and mobile behavior.  
   **Status:** DONE  
   **Notes:** Completed with compact jobs header mode and reduced duplicate copy on narrow viewports.

5. **ID:** PJR-UI-05  
   **Title:** Compact and simplify filters for narrow screens  
   **Rationale:** Existing filter density and wording create unnecessary interaction cost on phones.  
   **Target screens/components:** Jobs filter summary, filter sheet layout, state toggles.  
   **Likely files to change:** `pythonista_job_runner/app/webui_html/20_jobs.html`, `pythonista_job_runner/app/webui_css/10_layout.css`, `pythonista_job_runner/app/webui_css/50_responsive.css`, `pythonista_job_runner/app/webui_js/10_render_search.js` (if summary tweaks needed).  
   **Tests to add or update:** Mobile filter interaction test and CSS guardrail for compact sheet controls.  
   **Status:** DONE  
   **Notes:** Completed with shorter summary/microcopy, compact toggle geometry, and tighter mobile filter sheet layout.

6. **ID:** PJR-UI-06  
   **Title:** Strengthen status semantics beyond color  
   **Rationale:** Shapes/icons/hierarchy improve readability for color-impaired and high-stress scanning.  
   **Target screens/components:** Job rows, state banners, pills, timeline states.  
   **Likely files to change:** `webui_html/20_jobs.html`, `webui_html/30_detail.html`, `webui_css/20_jobs_table.css`, `webui_css/10_layout.css`.  
   **Tests to add or update:** State icon and semantics assertions in unit/e2e.  
   **Status:** DONE  
   **Notes:** Completed by semantic badge labels/ARIA details plus non-color shape cues and detail-banner badge rendering.

7. **ID:** PJR-UI-07  
   **Title:** Refine microcopy for next-action clarity  
   **Rationale:** Copy should direct operators to action, not only describe interface sections.  
   **Target screens/components:** Jobs intro, setup hints, empty states, detail helper text.  
   **Likely files to change:** `webui_html/20_jobs.html`, `webui_html/42_setup.html`, `webui_html/30_detail.html`.  
   **Tests to add or update:** Bundle text guardrails for action-oriented phrasing.  
   **Status:** DONE  
   **Notes:** Completed with action-first copy on jobs, setup, and disconnected/filtered empty states.

8. **ID:** PJR-UI-08  
   **Title:** Add progressive disclosure to setup and advanced panels  
   **Rationale:** Low-frequency technical content should not compete with primary operator path.  
   **Target screens/components:** Setup modal, advanced modal.  
   **Likely files to change:** `webui_html/42_setup.html`, `webui_html/40_advanced.html`, `webui_css/40_overlays.css`.  
   **Tests to add or update:** Assertions for collapsed-by-default advanced sections.  
   **Status:** DONE  
   **Notes:** Completed by keeping package sections collapsed by default in Advanced and adding guided caution note.

9. **ID:** PJR-UI-09  
   **Title:** Align visual language with Home Assistant patterns  
   **Rationale:** Native-feeling controls improve trust and reduce context-switch cost.  
   **Target screens/components:** Buttons, chips, cards, spacing cadence across app.  
   **Likely files to change:** `webui_css/00_tokens.css`, `webui_css/10_layout.css`, `webui_css/20_jobs_table.css`.  
   **Tests to add or update:** Visual regression snapshots and token guardrails.  
   **Status:** DONE  
   **Notes:** Completed lightweight HA-context cues in jobs/support copy and calmer advanced disclosure treatment without stack rewrite.

10. **ID:** PJR-UI-10  
   **Title:** Delay machine metadata prominence in job rows  
   **Rationale:** Operators should parse outcome and recency before IDs/technical fields.  
   **Target screens/components:** Jobs table row rendering and mobile cards.  
   **Likely files to change:** `webui_js/10_render_search.js`, `webui_css/20_jobs_table.css`.  
   **Tests to add or update:** Row content-order and mobile card scanability checks.  
   **Status:** DONE  
   **Notes:** Completed by making operator-first row title/state primary and moving raw Job ID into secondary muted line.

11. **ID:** PJR-UI-11  
   **Title:** Systematise action placement by role  
   **Rationale:** Predictable action location reduces mis-click and cognitive load.  
   **Target screens/components:** Header, jobs toolbar, detail actions, modals.  
   **Likely files to change:** `webui_html/00_shell.html`, `webui_html/20_jobs.html`, `webui_html/30_detail.html`, `webui_css/10_layout.css`.  
   **Tests to add or update:** Interaction tests validating action location consistency.  
   **Status:** DONE  
   **Notes:** Added reusable action-role attributes and consistent ordering for primary/destructive/overflow actions.

12. **ID:** PJR-UI-12  
   **Title:** Improve empty and low-data guidance states  
   **Rationale:** Low-data screens should direct next steps clearly and reassure progress.  
   **Target screens/components:** Jobs empty/loading/disconnected states.  
   **Likely files to change:** `webui_html/20_jobs.html`, `webui_js/10_render_search.js`, `webui_css/20_jobs_table.css`.  
   **Tests to add or update:** State copy + CTA presence tests, interaction assertions.  
   **Status:** DONE  
   **Notes:** Added state-aware empty icon treatment and retry action for disconnected mode plus stronger filtered guidance.

13. **ID:** PJR-UI-13  
   **Title:** Strengthen segmented detail view distinction  
   **Rationale:** Tabs should feel like clear mode changes rather than weak chip toggles.  
   **Target screens/components:** Detail tabs and active-state treatment.  
   **Likely files to change:** `webui_html/30_detail.html`, `webui_css/20_jobs_table.css`.  
   **Tests to add or update:** Tab semantics and active-mode visual cue tests.  
   **Status:** DONE  
   **Notes:** Wrapped detail tabs in segmented shell and strengthened active-tab shape/contrast cues.

14. **ID:** PJR-UI-14  
   **Title:** Separate routine info from diagnostics hierarchy  
   **Rationale:** Operators need a clear divide between everyday use and deep troubleshooting.  
   **Target screens/components:** Detail overview cards, metadata, request/API blocks.  
   **Likely files to change:** `webui_html/30_detail.html`, `webui_css/10_layout.css`.  
   **Tests to add or update:** Structure tests for routine-first ordering.  
   **Status:** DONE  
   **Notes:** Added explicit Routine checks vs Advanced diagnostics labels and grouped metadata/API under advanced section markers.

15. **ID:** PJR-UI-15  
   **Title:** Introduce stronger section rhythm and cadence  
   **Rationale:** Consistent section separation accelerates scanning and reduces monotony.  
   **Target screens/components:** All major cards and section boundaries.  
   **Likely files to change:** `webui_css/10_layout.css`, `webui_css/20_jobs_table.css`, `webui_css/40_overlays.css`.  
   **Tests to add or update:** CSS guardrails for section spacing tokens.  
   **Status:** DONE  
   **Notes:** Added reusable section-kicker rhythm pattern and increased segmented-shell/summary spacing cadence.

16. **ID:** PJR-UI-16  
   **Title:** Redesign job rows around human recognition  
   **Rationale:** Row structure should emphasize state, actor, and timing before raw IDs.  
   **Target screens/components:** Jobs list row template (desktop + mobile).  
   **Likely files to change:** `webui_js/10_render_search.js`, `webui_css/20_jobs_table.css`.  
   **Tests to add or update:** Row content hierarchy tests and Playwright mobile checks.  
   **Status:** DONE  
   **Notes:** Row headings now lead with actor + state while age/duration and urgency cues precede raw IDs; delayed/long-running markers are surfaced in-row.

17. **ID:** PJR-UI-17  
   **Title:** Standardise app-wide action architecture  
   **Rationale:** Distinct global/section/inline/overflow patterns reduce ambiguity.  
   **Target screens/components:** Header menu, jobs actions, detail action rows, modal action bars.  
   **Likely files to change:** `webui_html/00_shell.html`, `webui_html/20_jobs.html`, `webui_html/30_detail.html`, `webui_css/10_layout.css`.  
   **Tests to add or update:** Action-role tests in bundle and interaction specs.  
   **Status:** DONE  
   **Notes:** Extended action-role semantics into row-level primary/inline/overflow controls and harmonised role-specific visual affordances.

18. **ID:** PJR-UI-18  
   **Title:** Collapse technical depth by default  
   **Rationale:** Advanced diagnostics should be discoverable but not dominant in first read.  
   **Target screens/components:** Detail metadata/API, setup advanced sections, advanced modal.  
   **Likely files to change:** `webui_html/30_detail.html`, `webui_html/42_setup.html`, `webui_html/40_advanced.html`.  
   **Tests to add or update:** Default collapsed-state assertions.  
   **Status:** DONE  
   **Notes:** Wrapped detail diagnostics in a closed advanced shell so routine summary content remains first while metadata/API stay one tap away.

19. **ID:** PJR-UI-19  
   **Title:** Add explicit triage layer for urgent attention  
   **Rationale:** UI should expose what requires immediate action at first glance.  
   **Target screens/components:** Queue summary, jobs toolbar, detail header banners.  
   **Likely files to change:** `webui_html/10_overview.html`, `webui_html/20_jobs.html`, `webui_js/10_render_search.js`.  
   **Tests to add or update:** Triage ordering and urgent-state surfacing tests.  
   **Status:** DONE  
   **Notes:** Added a jobs triage strip with urgent-state styling and direct filters for errors/running/queued plus delayed/long-running counts.

20. **ID:** PJR-UI-20  
   **Title:** Make time information decision-friendly  
   **Rationale:** Operators should quickly see recency, staleness, and long-running risk.  
   **Target screens/components:** Jobs age/duration columns, detail timeline.  
   **Likely files to change:** `webui_js/10_render_search.js`, `webui_js/20_detail_meta.js`, `webui_css/20_jobs_table.css`.  
   **Tests to add or update:** Time-format and stale/active treatment tests.  
   **Status:** DONE  
   **Notes:** Added delayed/long-running time cues in rows, triage counters, and detail context chips/result copy keyed to age and duration.

21. **ID:** PJR-UI-21  
   **Title:** Clarify healthy success/completion states  
   **Rationale:** Positive completion should read as resolved, not merely absence of failure.  
   **Target screens/components:** Done badges, detail success summaries, empty-success hints.  
   **Likely files to change:** `webui_html/30_detail.html`, `webui_css/10_layout.css`, `webui_css/20_jobs_table.css`.  
   **Tests to add or update:** Done-state microcopy/semantics tests.  
   **Status:** DONE  
   **Notes:** Reframed done-state copy around “resolved successfully” in rows, banner title, and detail summaries to reduce ambiguity.

22. **ID:** PJR-UI-22  
   **Title:** Differentiate action risk levels  
   **Rationale:** Harmless vs state-changing vs destructive actions require clear affordance differences.  
   **Target screens/components:** Header/menu buttons, row actions, destructive dialogs.  
   **Likely files to change:** `webui_html/00_shell.html`, `webui_html/30_detail.html`, `webui_css/10_layout.css`, `webui_css/40_overlays.css`.  
   **Tests to add or update:** Class/role tests for risk-coded actions.  
   **Status:** DONE  
   **Notes:** Added explicit `data-risk-level` semantics (harmless/state-change/destructive) across global, row, detail, and maintenance controls with matching visual treatment.

23. **ID:** PJR-UI-23  
   **Title:** Strengthen “where am I?” context cues  
   **Rationale:** Users need persistent host/job/mode/scope orientation while navigating.  
   **Target screens/components:** Header context pills, detail breadcrumb, tab labels.  
   **Likely files to change:** `webui_html/00_shell.html`, `webui_html/30_detail.html`, `webui_js/20_detail_meta.js`.  
   **Tests to add or update:** Context-cue presence tests in bundle and interactions.  
   **Status:** DONE  
   **Notes:** Added a persistent mode pill and synchronized jobs/detail+tab context labeling, plus reinforced detail scope/actor/age/duration cues.

24. **ID:** PJR-UI-24  
   **Title:** Make content density elastic by surface type  
   **Rationale:** Lists, forms, and reading areas need different density defaults to stay legible.  
   **Target screens/components:** Tables, setup forms, detail reading panes.  
   **Likely files to change:** `webui_css/10_layout.css`, `webui_css/20_jobs_table.css`, `webui_css/40_overlays.css`.  
   **Tests to add or update:** Density mode and responsive guardrail tests.  
   **Status:** DONE  
   **Notes:** Introduced surface-specific density tokens so list rows, form shells, and reading panes scale together under comfortable/compact modes.

25. **ID:** PJR-UI-25  
   **Title:** Layer inline help progressively  
   **Rationale:** Keep first-level screens clean while preserving deeper explanatory help on demand.  
   **Target screens/components:** Setup hints, help modal, advanced detail hints.  
   **Likely files to change:** `webui_html/42_setup.html`, `webui_html/50_help.html`, `webui_css/40_overlays.css`.  
   **Tests to add or update:** Help-expansion behavior tests.  
   **Status:** DONE  
   **Notes:** Added collapsed inline-help disclosures in Setup steps, Help quick start rationale, and Detail troubleshooting guidance.

26. **ID:** PJR-UI-26  
   **Title:** Establish obvious primary path per major screen  
   **Rationale:** Recommended next actions should stand out without reading every control.  
   **Target screens/components:** Jobs toolbar, detail action strip, setup primary step.  
   **Likely files to change:** `webui_html/20_jobs.html`, `webui_html/30_detail.html`, `webui_html/42_setup.html`, `webui_css/10_layout.css`.  
   **Tests to add or update:** CTA prominence and action order checks.  
   **Status:** DONE  
   **Notes:** Added explicit primary-path strips in Jobs and Setup plus a detail primary-path cue with a one-tap “Open priority job” action.

27. **ID:** PJR-UI-27  
   **Title:** Improve overview-to-detail transition coherence  
   **Rationale:** Navigation depth should preserve context and reduce reorientation cost.  
   **Target screens/components:** Jobs row selection, detail breadcrumb/topline, summary handoff.  
   **Likely files to change:** `webui_js/10_render_search.js`, `webui_js/20_detail_meta.js`, `webui_html/30_detail.html`.  
   **Tests to add or update:** Interaction tests validating contextual handoff from list to detail.  
   **Status:** DONE  
   **Notes:** Added a detail handoff panel populated from the selected jobs row (actor/state/age) to preserve context during list-to-detail transitions.
