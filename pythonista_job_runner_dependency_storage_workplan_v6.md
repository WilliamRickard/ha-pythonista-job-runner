Version: 6

# Pythonista Job Runner dependency storage and package management workplan

## Goal

Add a persistent, sandboxed dependency layer to the Home Assistant add-on so jobs do not need to reinstall the same Python packages on every run, while keeping job execution isolated and keeping user-managed package files separate from private internal cache state.

This plan is driven by the failures seen in Example 5. The current implementation installs `requirements.txt` into a per-job `_deps` folder and uses `--no-cache-dir`, which is simple but guarantees repeated work and makes fast, reliable offline reuse impossible.

## Recommended end state

Use a three-layer design:

1. A private persistent package store under `/data` for pip cache, wheelhouse files, reusable virtual environments, manifests, and eviction metadata.
2. An optional user-visible package area under `/config` using `addon_config:rw` for uploaded wheels, constraints files, package profile definitions, and exported diagnostics.
3. Per-job execution that stays ephemeral, but can attach to a prepared dependency environment by profile or by resolved requirements hash.

This keeps secrets and internal state out of the user-visible area, but still gives the user a clean way to provide package inputs and inspect debug outputs.

## Why this design

Home Assistant currently supports mapped folders including `addon_config`, `all_addon_configs`, `share`, `media`, and `data`, and `addon_config:rw` is the documented way to expose add-on-specific files to users while keeping them included in add-on backups. That makes it the right place for user-managed wheels and profile files, not `config` or `share`. Date checked: 2026-03-10. Source: Home Assistant developer docs and blog. See References.

pip already supports on-by-default caching, `--find-links` based wheelhouse installs, JSON install reports, and local requirements entries. Python’s built-in `venv` remains the standard supported way to create isolated environments. Date checked: 2026-03-10. Source: official pip and Python docs. See References.

## Non-goals for this workstream

- No support for arbitrary compiled toolchains in this phase. Rust and C++ remain separate work.
- No global writable site-packages shared directly across jobs.
- No Home Assistant Supervisor disk quota dependency. Any storage limits must be enforced by the add-on itself.
- No assumption that internet access exists at runtime.

## Current state in the repo

Relevant current files:

- `pythonista_job_runner/config.yaml`
- `pythonista_job_runner/translations/en.yaml`
- `pythonista_job_runner/DOCS.md`
- `pythonista_job_runner/app/runner/deps.py`
- `pythonista_job_runner/app/runner/executor.py`
- `pythonista_job_runner/app/runner/results.py`
- `pythonista_job_runner/app/runner/store*.py`
- `pythonista_job_runner/app/http_api_server.py`
- `pythonista_job_runner/app/webui.html`
- `pythonista_job_runner/app/webui.js`
- `pythonista_job_runner/app/webui.css`
- `custom_components/pythonista_job_runner/*`

Current behaviour to replace or extend:

- dependency install is all-or-nothing per job
- install target is `_deps` under the job work directory
- pip is forced to `--no-cache-dir`
- there is no persistent wheelhouse
- there are no named package profiles
- there is no package storage UI or diagnostics view
- there is no app-managed storage limit or pruning

## Target storage layout

### Private internal storage

Use a dedicated tree under `/data/pythonista_job_runner/`:

```text
/data/pythonista_job_runner/
  cache/
    pip/
    http/
  wheelhouse/
    downloaded/
    built/
    imported/
  venvs/
    <environment-key>/
  profiles/
    manifests/
    locks/
  jobs/
    package_reports/
  state/
    package_index.json
    venv_index.json
    eviction_log.json
    storage_stats.json
```

Notes:

- `cache/pip/` backs `PIP_CACHE_DIR`.
- `wheelhouse/downloaded/` stores packages pulled from indexes.
- `wheelhouse/imported/` stores user-supplied wheels copied from `/config` after validation.
- `venvs/<environment-key>/` stores reusable isolated environments.
- `state/` stores app-owned metadata used for reuse, pruning, and diagnostics.

### Public user-visible storage

Use `addon_config:rw` mapped to `/config` inside the add-on:

```text
/config/
  package_profiles/
    default/
      requirements.in
      requirements.lock
      constraints.txt
      README.md
  wheel_uploads/
  diagnostics/
  exports/
```

Rules:

- `/config/package_profiles/` is for user-authored profile inputs.
- `/config/wheel_uploads/` is for manual wheel bundles and local package files.
- `/config/diagnostics/` is for user-visible exported package reports.
- The add-on should never execute code directly from `/config`; it should validate and copy selected artefacts into `/data` first.

## Proposed configuration changes

Update `pythonista_job_runner/config.yaml` and translations.

### New `python` options

```yaml
python:
  install_requirements: false
  dependency_mode: "per_job"
  package_cache_enabled: true
  package_cache_max_mb: 2048
  package_cache_prune_on_start: true
  package_profiles_enabled: true
  package_profile_default: ""
  package_allow_public_wheelhouse: true
  package_public_wheelhouse_subdir: "wheel_uploads"
  package_require_hashes: false
  package_offline_prefer_local: true
  venv_reuse_enabled: true
  venv_max_count: 20
  pip_timeout_seconds: 120
  pip_index_url: ""
  pip_extra_index_url: ""
  pip_trusted_hosts: []
  allow_env: []
```

### Suggested schema additions

```yaml
python:
  install_requirements: bool
  dependency_mode: "list(disabled|per_job|profile)"
  package_cache_enabled: bool
  package_cache_max_mb: "int(256,65536)"
  package_cache_prune_on_start: bool
  package_profiles_enabled: bool
  package_profile_default: str
  package_allow_public_wheelhouse: bool
  package_public_wheelhouse_subdir: str
  package_require_hashes: bool
  package_offline_prefer_local: bool
  venv_reuse_enabled: bool
  venv_max_count: "int(0,500)"
  pip_timeout_seconds: "int(10,3600)"
  pip_index_url: str
  pip_extra_index_url: str
  pip_trusted_hosts:
    - str
  allow_env:
    - str
```

### Add-on config mapping changes

Add `addon_config:rw` to `map` so `/config` becomes the app-specific public storage area.

Do not map full `config`.

## Proposed package model

### Execution modes

`disabled`
: Ignore `requirements.txt` and do not attach any reusable environment.

`per_job`
: Use the job’s own `requirements.txt`, but resolve it using the persistent cache and wheelhouse. If a matching reusable venv already exists and policy allows reuse, attach that instead of reinstalling.

`profile`
: Ignore or optionally merge job `requirements.txt`; instead attach a named prepared environment from the package profile store.

### Package profiles

A package profile is a named, versioned dependency definition with metadata.

Suggested profile manifest shape:

```json
{
  "name": "data_tools_basic",
  "display_name": "Data tools basic",
  "python": "3.12",
  "requirements_lock": "requirements.lock",
  "constraints": "constraints.txt",
  "require_hashes": true,
  "allow_job_overlay": false,
  "created_at": "2026-03-10T00:00:00Z"
}
```

### Environment key

Compute reusable venv keys from:

- Python version
- architecture
- dependency mode
- normalised requirements hash or profile lock hash
- pip index policy
- hash enforcement flag
- offline-prefer-local flag

This prevents accidental cross-use of incompatible environments.

## Web UI changes

Add a new top-level area or tab: `Packages`.

### Packages overview card

Show:

- dependency mode
- package cache enabled or disabled
- package cache size used
- wheelhouse item count
- reusable venv count
- default profile
- offline-prefer-local state

### Package profiles table

Columns:

- profile name
- Python version
- status
- lock hash
- venv ready
- last built
- size
- actions

Actions:

- build
- rebuild
- export diagnostics
- delete

### Cache diagnostics panel

Show:

- pip cache path
- wheelhouse path
- venv root path
- bytes used by each
- last prune result
- cache hit or miss for most recent job
- install duration for most recent job

### Job details changes

For each job, show:

- dependency source: none, per-job, profile
- selected profile name if any
- resolved environment key
- cache hit, wheelhouse hit, or full install
- pip install report path if generated
- pip inspect report path if generated

### Download and export actions

Allow export of:

- install report JSON
- inspect report JSON
- effective requirements lock
- wheelhouse manifest
- package diagnostics bundle

## API changes

Extend the add-on API with package endpoints. Keep them internal to the add-on HTTP API first.

Suggested endpoints:

- `GET /packages/summary.json`
- `GET /packages/profiles.json`
- `POST /packages/profiles/<name>/build`
- `POST /packages/profiles/<name>/rebuild`
- `DELETE /packages/profiles/<name>`
- `GET /packages/cache.json`
- `POST /packages/cache/prune`
- `POST /packages/cache/purge`
- `GET /packages/jobs/<job_id>.json`
- `GET /packages/exports/<name>.zip`

Return JSON only. Any destructive action must be explicit.

## Internal implementation outline

### New modules

Add new modules under `pythonista_job_runner/app/runner/`:

- `package_store.py`
- `package_profiles.py`
- `package_envs.py`
- `package_reports.py`
- `package_prune.py`
- `package_hashes.py`
- `package_public.py`

### Existing modules to change

`deps.py`
: replace single per-job install flow with orchestration into cache, wheelhouse, and reusable venv layers.

`executor.py`
: attach prepared environment to the job run and persist package outcome metadata.

`results.py`
: include package diagnostics artefacts in result zips, subject to limits.

`runner_core.py`
: load new options and expose them to dependency logic.

`http_api_server.py`
: add package endpoints.

`webui.html`, `webui.js`, `webui.css`
: add Packages area and job diagnostics rendering.

`config.yaml`, translations, docs
: add user-facing config and help text.

## Phase plan

### Phase 1. Design lock and storage foundation

Status: implemented in this repo update.

Deliverables completed:

- added `map: addon_config:rw` to `config.yaml` with `path: /config`
- added the new Python package options to `config.yaml` and translations
- created `pythonista_job_runner/app/runner/package_store.py` for storage path helpers and bootstrap
- added package state index files under `/data/pythonista_job_runner/state/`
- added unit tests for path resolution, bootstrap, and runner startup integration
- updated `DOCS.md` with the storage model overview

Implementation notes:

- Phase 1 deliberately does not change the current `requirements.txt` install path. Jobs still install into per-job `_deps`.
- The bootstrap now creates the private package tree on runner startup and prepares public `/config` subdirectories only when `/config` already exists.
- `storage_stats.json` is initialised as metadata only. Actual pruning, usage accounting, and cache behaviour are deferred to later phases.

Acceptance criteria status:

- add-on starts cleanly with new options present: implemented by config and runner startup changes
- `/data/pythonista_job_runner/` is created on startup: covered by runner startup tests
- `/config` is available when `addon_config:rw` is enabled: covered by config mapping and bootstrap tests
- no change yet to actual package install behaviour: preserved

### Phase 2. pip cache reuse and install diagnostics

Status: implemented in this repo update.

Deliverables completed:

- removed `--no-cache-dir` from the per-job dependency install path
- set `PIP_CACHE_DIR` to the private package cache directory when cache is enabled
- added `pip install --report` output per install under the private package report directory
- added best-effort `pip inspect --path <_deps>` output after successful installs
- persisted per-job package diagnostics metadata on the job status payload and as `package_diagnostics.json`
- surfaced basic package diagnostics in the job details Web UI
- bundled package report files into `result.zip` under `package/`

Implementation notes:

- The install target remains the per-job `_deps` folder. This phase adds cache reuse and diagnostics only; it does not yet introduce local wheelhouse selection or reusable virtual environments.
- Cache hit detection is a lightweight heuristic based on pip output containing `Using cached`. It is good enough for Phase 2 job diagnostics, but Phase 3 and Phase 4 should replace it with richer package provenance metadata.
- `pip inspect` is treated as best-effort. Install success still stands even if inspect output cannot be produced.

Acceptance criteria status:

- repeated per-job installs can reuse the same pip cache directory: implemented by `PIP_CACHE_DIR` wiring
- result zip includes install report and inspect report when available: implemented by package result bundling
- Web UI shows package cache and report details on the job detail view: implemented
- Example 5 style job can now benefit from cache reuse on later runs when remote access is available: implementation in place; user validation remains for a later package example rerun

Deliverables:

- remove `--no-cache-dir` from the dependency install path
- set `PIP_CACHE_DIR` to the private cache directory when cache is enabled
- emit `pip install --report` JSON per install
- emit `pip inspect` JSON after successful install
- persist per-job package diagnostics metadata
- show basic package diagnostics on the job details page

Acceptance criteria:

- repeated per-job installs hit the same pip cache
- result zip includes install report and inspect report when available
- Web UI shows whether the last run used cache
- Example 5 style job becomes repeatably faster on second run when internet is available

### Phase 3. Local wheelhouse and offline-first installs

Status: implemented in this repo update.

Deliverables completed:

- extended `package_store.py` with wheelhouse scans, package index refresh, validated public wheel import, and deterministic `--find-links` directory discovery
- imported validated wheel files from `/config/wheel_uploads/` into `/data/pythonista_job_runner/wheelhouse/imported/`
- added offline-first dependency install logic that tries local wheelhouse sources with `--no-index` before falling back to remote indexes
- added best-effort `pip download` and `pip wheel` preparation steps to warm the persistent wheelhouse after successful installs
- expanded per-job package diagnostics with wheelhouse counts, source selection, local-only attempt status, public wheel sync results, and preparation status
- surfaced wheelhouse-related fields in the job details Web UI metadata view
- updated package docs and tests for wheelhouse import and offline-first behaviour

Implementation notes:

- the install target still remains the per-job `_deps` folder. This phase only changes how pip resolves and prepares dependency artefacts.
- local wheel sources are discovered from the persistent imported, downloaded, and built wheelhouse directories, plus job-local `vendor/` and `wheels/` folders when present.
- when **Prefer local packages before remote indexes** is enabled and wheel sources exist, the runner now tries a local-only `--no-index` install first. If that fails, it falls back to the normal pip index flow while still keeping `--find-links` active.
- wheelhouse preparation remains best-effort. A successful install stands even if the later `pip download` or `pip wheel` warm-up step fails.

Acceptance criteria status:

- a job can install from local wheelhouse without remote index access: implemented by the local-only `--no-index` install path
- imported wheels from `/config` are validated and copied into `/data`: implemented by the public wheel import sync
- logs and diagnostics make clear whether install used remote index, local wheelhouse, or both: implemented by package status metadata, report files, and Web UI metadata rows

### Phase 4. Reusable virtual environments

Status: implemented in this repo update.

Deliverables completed:

- added `runner/package_envs.py` for reusable-venv keys, attach logic, index updates, and pruning
- build environment keys from Python version, architecture, dependency definition hash, and policy flags
- create keyed venvs under `/data/pythonista_job_runner/venvs/` using `python3 -m venv`
- reuse ready keyed venvs on later runs by prepending the venv `bin/` directory to `PATH` and setting `VIRTUAL_ENV`
- persist reusable-venv metadata in `state/venv_index.json` and update `storage_stats.json` with venv counts and bytes
- add best-effort pruning down to `venv_max_count` using least-recently-used order, excluding the venv currently being attached
- surface reusable-venv diagnostics in package metadata, `summary.txt`, result manifests, and the job details Web UI
- add tests for environment key generation, venv index bookkeeping, pruning, venv creation, fallback, and reuse

Implementation notes:

- venv reuse is currently active for `dependency_mode: per_job` when **Install requirements.txt automatically** and **Reuse prepared virtual environments** are enabled. The first matching run builds the keyed venv. Later runs with the same requirements and package policy reuse it.
- if `python3 -m venv` fails, the add-on now falls back to the older per-job `_deps` install flow instead of failing immediately. That keeps the add-on usable on hosts where venv bootstrap is unavailable, and the fallback is recorded in package diagnostics.
- the current pruning logic is best-effort least-recently-used based on the persisted `last_used_utc` field. Active-environment protection beyond the currently attached key remains part of the later safety-rails phase.

Acceptance criteria status:

- second run with identical resolved requirements reuses the same venv: implemented and covered by tests
- runs with changed requirements build a new venv instead of mutating the old one: implemented via keyed environment hashes
- venv reuse works without polluting unrelated jobs: implemented by keyed isolated venv directories and attach-only reuse

### Phase 5. Package profiles

Status: implemented in this repo update.

Deliverables completed:

- added `/config/package_profiles/` discovery with support for one-folder-per-profile layouts
- added profile manifest support through `manifest.json` or `profile.json`
- added explicit profile build and rebuild commands through `POST /package_profiles/build`
- added `GET /package_profiles.json` so profile inventory and ready state are visible through the API
- enabled `dependency_mode: profile` using the configured default profile name
- reused keyed venvs for package profiles so one built profile can be attached across multiple jobs
- added package profile rows and build actions in the Advanced Web UI panel
- exported an effective requirements file, profile status JSON, and diagnostics bundle under `/config/exports/package_profiles/<profile>/` and `/config/diagnostics/package_profiles/<profile>/`
- surfaced attached profile metadata in job package diagnostics, result summaries, and the job detail metadata view
- added tests for profile discovery, build, attach, API routing, and Web UI wiring

Implementation notes:

- profile mode currently uses the configured **Default package profile**. The first matching job can build the profile automatically if it is not already ready, and later jobs reuse the prepared venv.
- profile discovery prefers `requirements.lock`, then `requirements.txt`, then `requirements.in`. If a `constraints.txt` file exists in the same profile folder it is applied during profile build.
- profile builds currently run synchronously through the API and through on-demand job attachment. That keeps the implementation simple and deterministic for now. Later phases can decide whether asynchronous build jobs are worth adding.
- profile diagnostics and exports are intentionally user-visible so the effective dependency definition and the latest build state are easy to inspect from Home Assistant backups.

Acceptance criteria status:

- user can define a profile once and reuse it across multiple jobs: implemented by keyed profile venv builds and attach-only reuse
- profile build is visible in Web UI and API: implemented by `/package_profiles.json`, `/package_profiles/build`, and the Advanced panel profile list and actions
- job run clearly shows which profile was attached: implemented through package metadata fields, result summaries, and detail-view metadata rows

### Phase 6. Pruning, limits, and safety rails

Deliverables:

- add package storage usage accounting
- enforce `package_cache_max_mb`
- prune by least recently used with protected active environments
- add manual cache prune and purge actions
- add optional hash-enforcement mode for lock files
- add validations for suspicious package paths, malformed local wheels, and oversized imports

Acceptance criteria:

- cache does not grow without bound
- active environment is never pruned mid-run
- prune actions are visible in audit and diagnostics

### Phase 7. Home Assistant integration surface and entity model

Deliverables:

- add integration entities for package cache size, venv count, last prune status, and default profile
- add service actions for profile build, cache prune, and cache purge
- expose diagnostics via the custom integration diagnostics flow
- update strings and translations

Acceptance criteria:

- package state is visible from Home Assistant proper, not only the add-on Web UI
- service actions can trigger profile build and prune work
- diagnostics download includes package subsystem state

### Phase 8. Docs, examples, and migration

Deliverables:

- update `README.md`, `DOCS.md`, and screenshots
- add at least three package-focused examples:
  - cached per-job requirements
  - offline wheelhouse install
  - named package profile run
- add migration notes from old per-job `_deps` behaviour
- update Pythonista runner docs to explain package modes and expected result artefacts

Acceptance criteria:

- Example 5 is replaced or expanded to prove the new model clearly
- docs explain when to use per-job mode versus profile mode
- examples include success criteria and troubleshooting

### Phase 99. Final hardening and release readiness

Deliverables:

- full regression pass across existing examples and new package examples
- stress test repeated runs, cache rebuilds, and prune cycles
- verify upgrade path from existing `0.6.13` installations
- verify backups restore `/config` package profiles correctly
- update changelog and release notes

Acceptance criteria:

- no regression to current basic job execution
- package features degrade cleanly when disabled
- user-visible docs and Web UI are consistent

## Testing plan

### Unit tests

Add tests for:

- environment key generation
- profile manifest validation
- wheel import validation
- path safety and no-symlink guarantees
- prune ordering and active-environment protection
- config option parsing

### Integration tests

Add tests for:

- repeated identical requirements leading to cache reuse
- offline install from local wheelhouse
- profile build then job run using profile mode
- result zip inclusion of install report and inspect report
- storage cap causing safe prune

### Manual user validation

Must include:

1. first run of Example 5 with empty cache
2. second run of Example 5 with warm cache
3. profile-based run without job requirements file
4. offline run using only imported wheelhouse files
5. prune run after cache exceeds configured size

## Risks and decisions to settle early

### Decision 1. `pip -t` versus venv-first execution

Recommendation: move toward venv-first execution as the steady state, but keep `pip -t` compatibility during migration. `venv` is the standard supported isolation model and is easier to reason about for reuse than repeatedly stitching directories into `PYTHONPATH`.

### Decision 2. Profile overlay rules

Recommendation: keep profile mode strict at first. Either use the selected profile as-is or fail if a job also supplies `requirements.txt`. Do not merge until the simpler model is stable.

### Decision 3. Public file trust model

Recommendation: never import directly from `/config` into execution. Validate, hash, and copy into `/data` first.

### Decision 4. Storage accounting scope

Recommendation: count all of pip cache, wheelhouse, reusable venvs, and exported package reports toward the package storage budget. Do not count ordinary job outputs.

## Recommended implementation order

Start with Phases 1 and 2 together in one branch. That gives immediate value with low risk.

Then do Phase 3 before Phase 5. Offline wheelhouse support is more important than profiles because it solves the example failure class directly.

Only do Phase 4 after the cache and wheelhouse layers are stable, otherwise you will lock in the wrong reuse model.

Suggested order:

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7
8. Phase 8
9. Phase 99

## First implementation slice I would take next

A practical first slice is:

- add `addon_config:rw`
- add new config options and translations
- create `/data/pythonista_job_runner/` storage bootstrap
- switch pip to use `PIP_CACHE_DIR`
- emit install report JSON and inspect report JSON
- show package diagnostics on the job details page

That is small enough to implement safely, solves part of the repeated-install pain immediately, and gives the observability needed before adding wheelhouse or reusable venv logic.

## References

Checked on 2026-03-10.

- Home Assistant developer docs, App configuration: `https://developers.home-assistant.io/docs/apps/configuration/`
- Home Assistant developer blog, Public Addon Config, 2023-11-06: `https://developers.home-assistant.io/blog/2023/11/06/public-addon-config/`
- pip docs, Caching: `https://pip.pypa.io/en/stable/topics/caching/`
- pip docs, `pip download`: `https://pip.pypa.io/en/stable/cli/pip_download/`
- pip docs, `pip wheel`: `https://pip.pypa.io/en/stable/cli/pip_wheel/`
- pip docs, Requirements File Format: `https://pip.pypa.io/en/stable/reference/requirements-file-format/`
- pip docs, Installation Report: `https://pip.pypa.io/en/stable/reference/installation-report/`
- pip docs, `pip inspect`: `https://pip.pypa.io/en/stable/reference/inspect-report/`
- Python docs, `venv`: `https://docs.python.org/3/library/venv.html`

## Progress log

### 2026-03-10 Phase 1 update

Implemented the storage foundation without changing dependency execution semantics. The repo now has a dedicated package storage helper module, config surface for future package modes, bootstrap state files under `/data/pythonista_job_runner/`, and docs that explain the private versus public storage split.

New files introduced in Phase 1:

- `pythonista_job_runner/app/runner/package_store.py`
- `pythonista_job_runner/tests/test_package_store.py`
- `pythonista_job_runner_dependency_storage_workplan_v2.md` in the repo root

Files materially changed in Phase 1:

- `pythonista_job_runner/config.yaml`
- `pythonista_job_runner/translations/en.yaml`
- `pythonista_job_runner/app/runner_core.py`
- `pythonista_job_runner/DOCS.md`
- `pythonista_job_runner/tests/test_runner_core_options_and_helpers.py`
- `pythonista_job_runner/tests/test_addon_packaging_guardrails.py`

Known carry-forward items into Phase 2:

- pip still runs with `--no-cache-dir` in `runner/deps.py`
- install and inspect reports are not yet emitted
- no package diagnostics are surfaced in the Web UI yet
