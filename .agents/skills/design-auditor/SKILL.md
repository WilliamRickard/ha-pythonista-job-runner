---
name: design-auditor
description: Use this skill when auditing a UI or frontend for design quality, accessibility, modernisation opportunities, or Home Assistant fit. Best for reviewing screenshots, HTML/CSS/JS, and responsive behaviour before implementation.
version: 1.0.0
---

# Design Auditor

Run a structured design audit before making UI changes.

## Inputs to inspect
- screenshots in `docs/ui_audit_screens/`
- relevant HTML, CSS, and JavaScript in the repo
- existing tests that describe UI behaviour

## Audit categories
Check the UI against these categories and state which matter most for the task:
1. Typography
2. Color and contrast
3. Spacing and layout
4. Visual hierarchy
5. Consistency
6. Accessibility
7. Forms and inputs
8. Motion and animation
9. Dark mode
10. Responsive and adaptive behaviour
11. Loading, empty, success, and error states
12. Content and microcopy
13. Internationalisation and expansion safety
14. Elevation and shadows
15. Iconography
16. Navigation patterns
17. Design tokens and variables

## Severity model
Use:
- Critical: blocks usability, accessibility, or operational clarity
- Warning: noticeably weakens the UI and should be fixed
- Tip: polish improvement, useful but not urgent

## Output structure
For every audit:
1. overall score out of 100
2. audit confidence
3. what is working well
4. critical issues
5. warnings
6. top 3 priority fixes
7. likely files to change

## Working rules
- Prefer evidence from code plus screenshots over screenshots alone.
- Distinguish operational clarity from visual polish.
- For Home Assistant add-on UI work, prioritise mobile-first usability and state communication.
- Do not recommend framework rewrites unless the current stack is clearly blocking the goal.
- Tie every major finding to specific screens and likely files.
- When asked to implement, start with the highest-leverage fixes first.
