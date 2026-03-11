Version: 0.6
# Pythonista Job Runner Upload Setup Workplan
Date: 2026-03-11

## Progress update

Completed on 2026-03-11:
- Work package E1 delivered as the docs-and-automated-hardening slice
- Updated the repository README, add-on guide, package example docs, changelog, and release-readiness checklist to describe the guided Setup workflow for wheel uploads, profile uploads, build and rebuild, restart guidance, and the new setup endpoints
- Added an end-to-end HTTP setup-flow test that exercises status, wheel upload, profile upload, profile build, and profile delete against the real handler layer with a fake build backend
- Updated the machine-readable API contract and contract tests to include `/setup/status.json`, `/setup/upload-wheel`, `/setup/upload-profile-zip`, `/setup/delete-wheel`, and `/setup/delete-profile`
- Ran a wider automated validation pass covering docs links, API contract checks, setup-flow tests, and the earlier package setup tests

Open item still requiring a real host:
- Work package E2 remains: manual iPhone and Home Assistant validation of the guided Setup flow, including native file-picker behaviour inside the Home Assistant app and Safari, plus a live example 5 run on a real add-on host

Completed on 2026-03-11:
- Work package A delivered as a read-only implementation slice
- Added backend readiness evaluation for the example 5 setup path
- Added authenticated `/setup/status.json` endpoint
- Added a new read-only Setup modal in the ingress UI
- Added refresh, status summaries, blockers, warnings, and next steps in the UI
- Work package B delivered as a backend upload slice
- Added authenticated `POST /setup/upload-wheel` endpoint
- Added authenticated `POST /setup/upload-profile-zip` endpoint
- Added wheel upload validation, safe temp-write, overwrite guard, and immediate wheelhouse sync
- Added profile-zip inspection, safe temp extraction, traversal and symlink rejection, overwrite guard, and readiness refresh in the response
- Added targeted automated tests for the new upload helpers and HTTP endpoints
- Work package C delivered as the interactive setup UI slice
- Added wheel and profile file-picker controls in the Setup modal for iPhone-friendly uploads
- Added overwrite confirmation in the UI when an uploaded wheel or profile name already exists
- Added delete flows in the UI for uploaded wheels and discovered profiles
- Added authenticated `POST /setup/delete-wheel` and `POST /setup/delete-profile` endpoints
- Added backend cleanup for deleted profiles, including cached exports, diagnostics, state, and reusable virtual environment removal when safe
- Added targeted automated tests for the new delete helpers, delete endpoints, and setup UI regressions
- Work package D delivered as the build-and-guidance slice
- Setup status now returns build availability, ready state, restart guidance, and a copyable suggested add-on config snippet
- The Setup modal now lets the user build or rebuild the target profile directly, without leaving the page
- Build and rebuild responses now refresh Setup state immediately and also refresh the package profile inventory
- The Setup modal now distinguishes restart-required, build-recommended, build-failed, and ready states in the banner and readiness summary
- Added targeted automated tests for the new setup-status fields, build response payloads, and setup UI actions

Notes from implementation:
- The Setup experience still uses a dedicated modal rather than a full route change, which fits the current single-page ingress architecture and keeps mobile behaviour consistent with the existing Help, Settings, and Advanced panels
- File upload now happens directly from the ingress page via native HTML file inputs, which should trigger the platform file picker on iPhone and Safari-compatible clients
- Replace is handled through an explicit confirm step after a name collision, rather than silent overwrite
- Profile uploads currently accept `manifest.json` plus a requirements-style file supported by the package system, including `requirements.txt` and `requirements.lock`
- The UI shows active upload, build, rebuild, and delete state in the banner and disables related controls while the request is running; byte-level progress bars remain optional future polish rather than a blocker for the first release
- The Setup page now uses one backend `ready_state` model so it can explain the difference between missing files, restart-required config drift, a failed build, and a merely unbuilt target profile
- The first release still stops short of editing Supervisor options automatically; it instead provides a copyable config snippet and explicit restart guidance

Next recommended implementation step:
- Work package E2: manual iPhone and Home Assistant validation, then final release-readiness sign-off

## Objective

Add an ingress-based setup flow to the Home Assistant add-on so a user can upload:
- a demo or real wheel into the add-on public wheel area
- a package profile as a zip into the package profiles area

The flow should make example 5 and similar profile-based runs practical from an iPhone, without shell access and without manually copying files into Home Assistant storage.

## Recommended delivery order

Build this in the existing add-on web UI. Do not try to force file upload into the Home Assistant add-on Configuration form.

Implement in this order:
1. Setup readiness contract and status endpoint
2. Read-only setup page
3. Secure wheel upload endpoint
4. Secure profile-zip upload endpoint
5. Replace and delete actions
6. Build-profile and recheck flow
7. Docs and test hardening
8. Manual iPhone and Home Assistant validation

## Scope

### In scope
- Backend status endpoint for setup readiness
- Backend upload endpoints for wheel files and profile zips
- Safe extraction and validation
- Ingress UI page for setup
- Status refresh and blocker reporting
- Delete and replace actions
- Profile build trigger from the setup page
- Documentation updates
- Automated tests for validation and safety

### Out of scope for first release
- Editing Supervisor add-on options automatically
- A custom integration or Home Assistant config flow
- Arbitrary package management beyond the defined upload contract
- Multi-user permissions model
- Bulk import of every file from a batch bundle in one click

## Success criteria

A user on iPhone can:
1. Open the add-on UI in Home Assistant
2. Go to a new Setup page
3. See whether the wheel and profile are present
4. Upload a wheel file
5. Upload a profile zip
6. See exact blockers if configuration is still wrong
7. Build the profile if needed
8. Restart the add-on after changing options
9. Return to Setup and see a clear ready state for example 5

## Assumptions

- The add-on already has `ingress: true`, `ingress_stream: true`, and `addon_config` mounted to `/config`
- `/config/wheel_uploads` remains the public wheel location
- `/config/package_profiles/<profile_name>` remains the profile location
- The package subsystem already has enough backend hooks to discover profiles and build them after files are in place
- The first release should optimise for the example 5 workflow, not for a general package marketplace

## Storage contract

### Canonical destinations
- Wheels: `/config/wheel_uploads/<filename>.whl`
- Profiles: `/config/package_profiles/<profile_name>/...`

### Accepted wheel input
- File extension must be `.whl`
- File name must be normalised and path-safe
- No nested paths accepted
- Existing file may be replaced only with explicit confirmation

### Accepted profile zip input
The uploaded zip must expand into exactly one profile root. Accept either:
- `demo_formatsize_profile/...`
- or a flat archive containing `manifest.json`, `requirements.txt`, and optional supporting files, which is then wrapped into a profile folder name derived from the manifest or filename

### Minimum required profile files
- `manifest.json`
- `requirements.txt` or `requirements.lock`

### Nice-to-have files
- `README.md`
- offline wheel references or supporting notes

### Rejection conditions
- Path traversal
- Absolute paths
- Symlinks if zip metadata exposes them
- More than one top-level profile root unless explicitly supported later
- Missing required files
- Unsupported extension
- Exceeds configured size limit

## Readiness model

Create one authoritative readiness model for the setup page.

### Status fields
- `wheel_present`
- `wheel_files`
- `profile_present`
- `profile_names`
- `default_profile`
- `default_profile_exists`
- `install_requirements_enabled`
- `dependency_mode`
- `package_profiles_enabled`
- `profile_built`
- `profile_build_available`
- `ready_for_example_5`
- `blockers`
- `warnings`
- `next_steps`

### Ready for example 5
`ready_for_example_5 = true` only if all of the below are true:
- at least one expected demo wheel is present, or a compatible wheelhouse source is present
- target profile exists
- `install_requirements` is enabled
- `package_profiles_enabled` is enabled
- `dependency_mode` is `profile`
- `package_profile_default` matches the target profile
- no current blocker indicates missing build prerequisites

## Phase plan

## Phase 1 - Lock the contract and backend readiness rules

### Goal
Define the exact supported upload contract and build one backend source of truth for setup readiness.

### Main tasks
- Decide exact accepted wheel and profile zip formats
- Define response schema for setup readiness
- Add backend helper functions that inspect:
  - `/config/wheel_uploads`
  - `/config/package_profiles`
  - current add-on options relevant to packages
  - profile discovery and build state
- Create a single readiness evaluation function that returns blockers and next steps
- Add clear internal naming:
  - setup target profile
  - setup target wheel
  - example 5 readiness

### Likely files
- `pythonista_job_runner/app/runner/package_store.py`
- `pythonista_job_runner/app/runner/package_profiles.py`
- `pythonista_job_runner/app/runner/deps.py`
- `pythonista_job_runner/app/http_api_server.py`
- tests under `pythonista_job_runner/tests/`

### Acceptance checks
- Backend can report readiness without running any job
- Missing wheel shows a precise blocker
- Missing profile shows a precise blocker
- Wrong dependency mode shows a precise blocker
- Wrong default profile shows a precise blocker
- Output is stable JSON with predictable keys

### Estimated size
Medium

## Phase 2 - Add a read-only Setup status endpoint and UI page

### Goal
Ship immediate value before uploads by showing users exactly what is missing.

### Main tasks
- Add a new HTTP endpoint such as `/api/setup/status`
- Add a new ingress UI page or tab called `Setup`
- Show:
  - current dependency mode
  - whether requirements installation is enabled
  - whether profile support is enabled
  - current default profile
  - whether the expected profile folder exists
  - whether the wheel upload area contains the expected wheel
  - whether example 5 is ready
  - blockers and next steps
- Add refresh action
- Add empty and error states

### UI requirements
- One top summary banner:
  - Ready
  - Not ready
  - Restart required
- Separate cards for:
  - Add-on settings
  - Uploaded wheel files
  - Package profiles
  - Example 5 readiness
- Keep mobile-first spacing and simple text

### Likely files
- `pythonista_job_runner/app/http_api_server.py`
- `pythonista_job_runner/app/webui_html/*`
- `pythonista_job_runner/app/webui_js/*`
- `pythonista_job_runner/app/webui_build.py`

### Acceptance checks
- Setup page loads on iPhone-sized viewport
- Setup page shows the exact missing item when wheel or profile is absent
- Refresh updates the state after backend changes
- No upload control yet, only status

### Estimated size
Medium

## Phase 3 - Backend wheel upload endpoint

### Goal
Allow secure upload of a wheel file into `/config/wheel_uploads`.

### Main tasks
- Add streamed upload endpoint, for example `/api/setup/upload-wheel`
- Save to a temp path first
- Validate:
  - extension is `.whl`
  - filename is path-safe
  - file is not empty
  - file does not exceed size limit
- Promote atomically into `/config/wheel_uploads`
- Support explicit overwrite mode
- Return updated readiness and uploaded filename
- Log enough detail for diagnosis without spamming secrets

### Error handling
- Reject invalid extensions with clear message
- Reject too-large files with clear message
- Reject overwrite unless explicitly allowed
- Clean temp files on failure

### Acceptance checks
- Valid wheel uploads successfully
- Existing wheel is not overwritten accidentally
- Overwrite works when requested
- Invalid extension is rejected
- Malformed filename is rejected
- Temp files are removed after failure

### Estimated size
Medium

## Phase 4 - Backend profile zip upload endpoint

### Goal
Allow secure upload of a package profile zip into `/config/package_profiles`.

### Main tasks
- Add streamed upload endpoint, for example `/api/setup/upload-profile-zip`
- Save upload to temp file
- Inspect zip before extraction
- Reject:
  - path traversal
  - absolute paths
  - symlinks
  - multiple ambiguous profile roots
  - missing required files
  - oversize archives or excessive entry counts
- Extract into a temporary directory
- Determine profile name
- Promote atomically into `/config/package_profiles/<profile_name>`
- Support explicit overwrite mode
- Return updated readiness, discovered profile name, and file summary

### Important design choice
Do not extract directly into the live destination. Always extract into temp, validate, then promote.

### Acceptance checks
- Valid profile zip uploads successfully
- Missing `manifest.json` is rejected
- Missing `requirements.txt` is rejected
- Traversal entries are rejected
- Existing profile is not overwritten accidentally
- Overwrite works when requested
- Failure does not leave partial directories

### Estimated size
Large

## Phase 5 - Add upload controls to the Setup page

### Goal
Make the setup page usable end-to-end from a phone.

### Main tasks
- Add wheel upload control
- Add profile zip upload control
- Show chosen filenames and upload progress
- Show success and failure messages inline
- Refresh readiness after upload automatically
- Add overwrite confirmation flow
- Show current uploaded wheel files and current profile folders
- Add delete buttons only after Phase 6 backend support is ready

### UX requirements
- Mobile-first layout
- No dense tables on small screens
- Clear destination labels:
  - `Uploads to /config/wheel_uploads`
  - `Uploads to /config/package_profiles`
- Explain accepted file formats next to controls
- Keep language practical and specific

### Acceptance checks
- On mobile viewport, wheel upload is usable without horizontal scrolling
- On mobile viewport, profile zip upload is usable without horizontal scrolling
- After upload, readiness updates automatically
- Clear error appears for invalid file
- The page remains usable after a failed upload

### Estimated size
Large

## Phase 6 - Add delete and replace actions

### Goal
Let the user recover from mistakes without shell access.

### Main tasks
- Add backend delete endpoint for wheel files
- Add backend delete endpoint for profile folders
- Add replace flow in UI for same-name uploads
- Add confirmation for destructive actions
- Refresh readiness after delete or replace

### Safeguards
- Only delete within the expected public config roots
- Require exact filename or profile name
- Reject empty or unsafe names
- Do not allow recursive deletion outside the profile root

### Acceptance checks
- User can delete an uploaded wheel
- User can delete an uploaded profile
- Readiness updates immediately after delete
- Unsafe names are rejected
- Deletion cannot escape managed directories

### Estimated size
Medium

## Phase 7 - Add build-profile and restart guidance flow

### Goal
Complete the operational flow for example 5.

### Main tasks
- Reuse or extend existing profile build endpoint from the Setup page
- Show build status and result
- Distinguish between:
  - files missing
  - build not yet run
  - build failed
  - restart required
  - wrong dependency mode
  - wrong default profile
  - ready to run example 5
- Add explicit restart guidance:
  - set `dependency_mode: profile`
  - set `package_profile_default`
  - restart add-on
  - return to Setup and refresh
- Consider a `Copy config snippet` helper in the UI

### Important boundary
Do not auto-edit Supervisor config in first release. Keep that manual but obvious.

### Acceptance checks
- User can trigger a profile build from Setup
- Failed build surfaces a useful message
- Success state shows the exact next step if restart or mode change is still needed
- Setup page shows ready once config matches and files are present

### Estimated size
Medium

## Phase 8 - Documentation and examples refresh

### Goal
Document the new setup flow clearly for real users.

### Main tasks
- Update main README
- Update package examples documentation
- Add a concise iPhone workflow
- Add screenshots or at least labelled UI descriptions
- Replace old manual copy guidance where appropriate
- Document supported archive layout and limits
- Document common blockers:
  - requirements disabled
  - wrong dependency mode
  - missing default profile
  - empty wheel uploads
  - permission problems if relevant

### Acceptance checks
- A new user can follow docs without shell access
- Docs match the final UI labels and endpoint behaviour
- Example 5 instructions use the new setup page flow

### Estimated size
Medium

## Phase 9 - Hardening and full test pass

### Goal
Make the feature safe and maintainable.

### Main tasks
- Add unit tests for readiness logic
- Add endpoint tests for wheel upload
- Add endpoint tests for profile zip upload
- Add tests for overwrite and delete
- Add archive safety tests:
  - traversal
  - absolute paths
  - duplicate roots
  - missing files
- Add UI smoke checks if current test stack supports them
- Manual test passes:
  - Home Assistant in mobile Safari
  - Home Assistant iOS app
  - desktop browser
- Re-run example workflow:
  - per_job setup for steps 1 to 4
  - profile setup for step 5

### Acceptance checks
- All new automated tests pass
- Existing test suite still passes
- Manual iPhone flow works without shell access
- Example 5 setup can be completed entirely from ingress plus the normal add-on restart/config change

### Estimated size
Large

## Suggested phase grouping for implementation

To keep phases balanced and reduce back-and-forth:

### Work package A
Phase 1 and Phase 2
- Contract
- Readiness logic
- Read-only Setup page

### Work package B
Phase 3 and Phase 4
- Wheel upload endpoint
- Profile zip upload endpoint
- Validation and safety
- Status: complete on 2026-03-11

### Work package C
Phase 5 and Phase 6
- Upload UI
- Replace and delete flows
- Status: next

### Work package D
Phase 7
- Build and restart guidance flow

### Work package E
Phase 8 and Phase 9
- Docs
- Hardening
- End-to-end checks

## Detailed acceptance checklist

## A. Readiness and status
- [ ] Setup status endpoint exists
- [ ] Response includes blockers, warnings, and next steps
- [ ] Response clearly distinguishes not uploaded from not configured
- [ ] Example 5 readiness is derived consistently from backend state

## B. Wheel upload
- [ ] `.whl` only
- [ ] Safe filename only
- [ ] Temp-write then atomic move
- [x] Overwrite requires confirmation
- [ ] Failures do not leave junk files

## C. Profile upload
- [ ] Zip inspected before extraction
- [ ] Traversal and absolute paths rejected
- [ ] Missing `manifest.json` rejected
- [ ] Missing `requirements.txt` rejected
- [ ] Temp extract then atomic move
- [x] Overwrite requires confirmation
- [ ] Failures do not leave partial profiles

## D. UI
- [ ] Setup page works on narrow mobile width
- [ ] Status is understandable without reading docs
- [ ] Inline errors are specific
- [x] After each successful action, status refreshes automatically

## E. Example 5 readiness
- [ ] User can see exact blocker before running a job
- [x] User can upload wheel and profile
- [ ] User can build profile
- [ ] User is told exactly which add-on config change is still needed
- [ ] After restart and recheck, page shows ready

## Risks and pitfalls

### Risk 1 - Upload safety bugs
Zip extraction is the highest-risk area. Keep all extraction in temp, validate aggressively, and add focused tests.

### Risk 2 - UI complexity creeping too far
A simple status-plus-upload page is enough for first release. Avoid turning it into a full package manager.

### Risk 3 - Trying to auto-edit add-on options too early
This adds complexity fast and is not required to solve the main user problem.

### Risk 4 - Ambiguous profile archive format
Lock the accepted format early and document it clearly.

### Risk 5 - Large file handling on mobile
Use streamed ingress endpoints and size limits. Show clear error messages on network or upload failure.

## Recommended next implementation step

Work package A through E1 are now complete in-repo. The remaining close-out work is live validation on a real Home Assistant host and iPhone client.
