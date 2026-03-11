<!-- Version: 0.6.14-docs.1 -->
# Pythonista Job Runner

Pythonista Job Runner is a Home Assistant add-on that accepts a job zip, extracts it into an isolated working directory, runs `run.py`, streams logs while it runs, and returns a result zip when it finishes.

It supports two access paths:

- **Ingress Web UI** inside Home Assistant for people using the built-in interface.
- **Direct HTTP API** on port `8787` for Pythonista and other clients.

## Task index

- [Install the repository and add-on](#install-the-repository-and-add-on)
- [Secure the add-on before you use it](#secure-the-add-on-before-you-use-it)
- [First run in the Web UI](#first-run-in-the-web-ui)
- [First run from Pythonista](#first-run-from-pythonista)
- [Ingress versus direct API access](#ingress-versus-direct-api-access)
- [Job zip format](#job-zip-format)
- [Result zip format](#result-zip-format)
- [Package storage foundation](#package-storage-foundation)
- [Choose the right package mode](#choose-the-right-package-mode)
- [Migration from older `_deps`-only behaviour](#migration-from-older-_deps-only-behaviour)
- [Release readiness and upgrade validation](#release-readiness-and-upgrade-validation)
- [Guided setup for profile-mode package uploads](#guided-setup-for-profile-mode-package-uploads)
- [Package example catalogue](#package-example-catalogue)
- [Pythonista client examples](#pythonista-client-examples)
- [HTTP API reference](#http-api-reference)
- [Troubleshooting](#troubleshooting)
- [Security and operating notes](#security-and-operating-notes)
- [Advanced and contributor notes](#advanced-and-contributor-notes)

## Install the repository and add-on

### Add the repository

1. In Home Assistant, go to **Settings -> Add-ons -> Add-on Store**.
2. Open the top-right menu and choose **Repositories**.
3. Add:
   `https://github.com/WilliamRickard/ha-pythonista-job-runner`

You can also use the My Home Assistant button in the repository [`README.md`](../README.md).

### Install the add-on

1. Find **Pythonista Job Runner** in the add-on store.
2. Install it.
3. Start it.
4. Open **Open Web UI** and confirm the jobs list loads.

## Secure the add-on before you use it

Set these options before you start using the direct API:

- **Access token**: direct API clients such as Pythonista must send this value in the `X-Runner-Token` header.
- **Ingress only**: when enabled, only Home Assistant Ingress can access the add-on. That blocks direct API calls from Pythonista.
- **Allowed client CIDRs**: when set, direct API requests must come from an allowed network as well as present the correct token.

Typical Pythonista setup:

1. Set a strong **Access token**.
2. Leave **Ingress only** off.
3. Optionally set **Allowed client CIDRs** to your local Wi-Fi subnet.

Do not expose port `8787` directly to the public internet. For remote access, use a virtual private network or another trusted path back to your home network.

For the full security model, read [`../SECURITY.md`](../SECURITY.md).

## First run in the Web UI

This is the fastest way to prove the add-on is healthy.

1. Open the add-on in Home Assistant.
2. Click **Open Web UI**.
3. Confirm the jobs list loads.
4. Confirm the UI can refresh without errors.
5. Confirm the settings and help panels open and scroll correctly on your device.

Once that works, the Ingress path is healthy and you can use the Web UI for day-to-day monitoring even if your actual job submission happens from Pythonista.

## First run from Pythonista

The add-on expects a raw zip request body, not a multipart form upload.

Your first job should be tiny. Put `run.py` at the zip root and write a single file under `outputs/`.

### Minimal `run.py`

```python
import os

print("Hello from Pythonista Job Runner")

os.makedirs("outputs", exist_ok=True)
with open("outputs/hello.txt", "w", encoding="utf-8") as f:
    f.write("It worked.
")
```

### Minimal Pythonista upload example

```python
import io
import zipfile

import requests

RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"
REQUEST_TIMEOUT_SECONDS = 60

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(
        "run.py",
        """import os
print('Hello from Pythonista Job Runner')
os.makedirs('outputs', exist_ok=True)
with open('outputs/hello.txt', 'w', encoding='utf-8') as f:
    f.write('It worked.\n')
""",
    )

response = requests.post(
    RUNNER_URL + "/run",
    data=buf.getvalue(),
    headers={
        "X-Runner-Token": TOKEN,
        "Content-Type": "application/zip",
    },
    timeout=REQUEST_TIMEOUT_SECONDS,
)
response.raise_for_status()

with open("result.zip", "wb") as f:
    f.write(response.content)

print("Saved result.zip")
```

A successful first run gives you a result zip that includes `stdout.txt`, `stderr.txt`, `status.json`, and `outputs/hello.txt`.

## Ingress versus direct API access

Use **Ingress** when you are interacting with the built-in Web UI from inside Home Assistant. Use the **direct API** when Pythonista or another client needs to upload a job zip over the network.

### Ingress

Ingress is the simplest path for people using the Web UI:

1. Open the add-on inside Home Assistant.
2. Click **Open Web UI**.
3. Browse jobs, logs, and result downloads from the authenticated Home Assistant session.

Ingress requests are authenticated by Home Assistant itself. You do not send `X-Runner-Token` manually in this flow.

### Direct API

The direct API is the path Pythonista uses. It goes to port `8787` on your Home Assistant host and requires `X-Runner-Token`. It only works when an Access token is set, **Ingress only** is off, and the client IP matches any configured CIDR allowlist.

Rule of thumb:

- Open Web UI inside Home Assistant: use Ingress.
- Upload from Pythonista on your phone: use the direct API.

## Job zip format

Your upload must be a zip file with `run.py` at the root.

- `run.py` is executed as the job entry point.
- Any other files in the zip are extracted into the job working directory.
- Files written under `outputs/` are included in the result zip.

### Optional `requirements.txt`

The add-on can optionally install dependencies listed in `requirements.txt` at the job root into a per-job directory.

This is off by default. To use it:

1. In add-on configuration, enable **Install requirements**.
2. Include `requirements.txt` in the job zip root.

Only enable this when you trust the code you are running.

## Result zip format

When the job completes, the result zip includes:

- `stdout.txt`
- `stderr.txt`
- `status.json`
- `exit_code.txt`
- `summary.txt`
- `result_manifest.json`
- `job.log`
- Optional pip install logs when requirement installation was used
- Your files under `outputs/`, if any

## Package storage foundation

The add-on now prepares a persistent package storage tree under `/data/pythonista_job_runner/`. This is private to the add-on and is used for pip cache files, wheelhouse data, reusable virtual environments, profile metadata, and package diagnostics.

Phase 6 adds storage safety rails on top of the earlier cache, wheelhouse, reusable-venv, and profile layers. The runner now:

- syncs validated wheel files from `/config/wheel_uploads/` into `/data/pythonista_job_runner/wheelhouse/imported/`
- rejects suspicious wheel filenames, malformed wheel archives, and oversized public wheel imports before they enter the private store
- passes internal wheelhouse directories to pip with `--find-links`
- tries a local-only `--no-index` install first when **Prefer local packages before remote indexes** is enabled
- creates a keyed venv under `/data/pythonista_job_runner/venvs/` for one unique requirements and policy combination
- reuses that keyed venv on later runs with the same requirements and install policy
- tracks reusable-venv metadata in `state/venv_index.json` and protects active environments from pruning while a job is running
- enforces the configured private package storage target with least-recently-used pruning and startup pruning when enabled
- records prune and purge activity in `state/eviction_log.jsonl` and `state/storage_stats.json`
- supports manual cache prune and purge actions through the API and the Advanced Web UI panel
- optionally enforces `--hash=` entries for `requirements.lock` files when **Require package hashes** is enabled
- writes wheelhouse, reusable-venv, and prune diagnostics into the package report area

The persistent directory layout is:

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

The add-on also maps `addon_config:rw` and expects that public add-on files are available at `/config` inside the container. This is the user-visible side of the package system. The add-on uses it for uploaded wheels, package profile files, exported diagnostics, and other package-related files that users may want to inspect or back up.

Reusable venv mode is now active when **Install requirements.txt automatically** and **Reuse prepared virtual environments** are enabled. The first matching run builds a keyed venv. Later runs with the same requirements and package policy reuse that venv by prepending its `bin/` directory to `PATH` and setting `VIRTUAL_ENV`.

If venv creation fails, the add-on falls back to the older per-job `_deps` install flow so jobs still have a working dependency path. That fallback is recorded in the package diagnostics and result summary.

### Package profiles

Phase 5 adds named package profiles under `/config/package_profiles/`. Each profile is one folder, for example:

```text
/config/package_profiles/data_tools_basic/
  manifest.json
  requirements.lock
  constraints.txt
```

The runner currently supports these files:

- `manifest.json` or `profile.json` for optional metadata such as `display_name`
- `requirements.lock`, `requirements.txt`, or `requirements.in` as the effective dependency source
- `constraints.txt` as an optional constraints file

When **Dependency handling mode** is set to `profile`, the add-on uses **Default package profile** to choose one of these folders, builds a keyed reusable venv for it, and attaches that environment to matching jobs.

Profile build exports are written under the public add-on config area so they are easy to inspect and back up:

```text
/config/exports/package_profiles/<profile-name>/
/config/diagnostics/package_profiles/<profile-name>/
```

Those exports include an effective requirements file, the latest profile status JSON, and a diagnostics zip bundle.

### Package cache limits and safety rails

The private package store now keeps usage accounting in `state/storage_stats.json` and enforces the configured **Package cache limit (MB)** target with best-effort least-recently-used pruning. Active reusable environments attached to running jobs are protected from pruning.

The add-on exposes these authenticated package cache endpoints:

- `GET /packages/cache.json`: current cache and storage summary.
- `POST /packages/cache/prune`: best-effort prune to the configured cache target while preserving active environments.
- `POST /packages/cache/purge`: clear cache areas and optionally remove reusable virtual environments and imported wheels.

The Advanced Web UI panel now exposes the same refresh, prune, and purge actions.

When **Require package hashes** is enabled, builds from `requirements.lock` now require `--hash=` entries on requirement lines. This is intended for locked dependency sets rather than loose `requirements.txt` files.

## Choose the right package mode

Use these rules:

- **disabled**: use this when the job is fully self-contained and should not install or attach any dependency environment.
- **per_job**: use this when the job zip carries its own `requirements.txt` and that definition is the source of truth for the run.
- **profile**: use this when several jobs should share one named prepared dependency environment from `/config/package_profiles/`.

A good default is still `per_job`. Switch to `profile` once the dependency set is stable and reused across multiple jobs.

## Migration from older `_deps`-only behaviour

Older versions of the add-on treated per-job dependencies as a one-shot install into a job-local `_deps` directory. That model still exists as a fallback, but it is no longer the main path.

What changed:

- repeated `per_job` runs can now reuse the persistent pip cache
- local wheels can be imported once into the private wheelhouse
- keyed reusable virtual environments can be attached across later matching runs
- named package profiles can build and reuse one prepared dependency environment for many jobs
- result bundles now include package diagnostics artefacts when the package subsystem was involved

What stays the same:

- the job contract is still `run.py` plus `outputs/`
- job execution still happens in an isolated working directory
- jobs can still run with no dependency handling at all

How to migrate safely:

1. Leave **Dependency handling mode** on `per_job` first.
2. Re-run one known package-aware job twice and inspect `package/package_diagnostics.json` plus `summary.txt`.
3. Import any shared wheels into `/config/wheel_uploads/` instead of bundling them into every job zip. The easiest path on iPhone is now the guided Setup modal in the Web UI.
4. Once the dependency set is stable, move it into `/config/package_profiles/<name>/` and switch matching jobs to `profile` mode. The guided Setup modal can upload the profile archive, build it, and tell you when the remaining step is a config save plus restart.

## Guided setup for profile-mode package uploads

Use the **Setup** modal in the Ingress Web UI when you need to prepare example 5 or any similar profile-mode run from an iPhone. This avoids manual shell access and avoids copying files into Home Assistant storage by hand.

What the Setup modal can do:

- show whether the target wheel, target profile, and current add-on settings line up
- upload one wheel into `/config/wheel_uploads/`
- upload one profile archive into `/config/package_profiles/`
- delete or replace uploaded setup artefacts when you picked the wrong file
- build or rebuild the target package profile
- show a copyable config snippet when the remaining blocker is add-on configuration rather than missing files

Recommended flow for example 5:

1. Open **Open Web UI** from the add-on page.
2. Open **Settings** or **Advanced**, then open **Setup**.
3. Check the readiness banner first. If it says files are missing, upload the wheel and profile zip from the same page.
4. If the page says the target profile exists but is not built, click **Build target profile**.
5. If the page says restart is required, copy the suggested config snippet, save the matching add-on options, and restart the add-on.
6. Return to **Setup** and refresh. When the page reports **Ready**, run example 5.

Accepted upload inputs:

- wheel uploads: one `.whl` file, stored under `/config/wheel_uploads/`
- profile uploads: one zip file that expands into exactly one profile folder, or one flat archive containing `manifest.json` plus `requirements.txt` or `requirements.lock`

The Setup endpoints exposed by the add-on are:

- `GET /setup/status.json`: return readiness, blockers, warnings, and next steps
- `POST /setup/upload-wheel`: upload one wheel file
- `POST /setup/upload-profile-zip`: upload one profile archive
- `POST /setup/delete-wheel`: delete one uploaded wheel
- `POST /setup/delete-profile`: delete one uploaded profile

These are authenticated endpoints intended for the built-in Web UI. Pythonista scripts can call them too, but the main reason they exist is to make the iPhone-first Web UI workflow practical.

## Package example catalogue

Package-focused examples now live under [`examples/packages/`](examples/packages/).

Use them in this order:

1. [`11_cached_per_job_requirements`](examples/packages/11_cached_per_job_requirements/README.md): run the same `per_job` dependency set twice and inspect reuse diagnostics.
2. [`12_offline_wheelhouse_install`](examples/packages/12_offline_wheelhouse_install/README.md): copy a wheel into the public add-on config, import it into the private wheelhouse, and install it without bundling the wheel inside the job zip.
3. [`13_named_package_profile_run`](examples/packages/13_named_package_profile_run/README.md): prepare a named package profile once, then run a job in `profile` mode with no job-local `requirements.txt`.

For Pythonista runs, keep looking at the job's own `outputs/` files first. Then inspect add-on-generated files such as `package/package_diagnostics.json`, `result_manifest.json`, `summary.txt`, and any profile diagnostics bundle the add-on exported.

## API contract

The machine-readable direct API contract lives at [`api/openapi.json`](api/openapi.json).

It is intended for client tooling, documentation sync, and regression checks.

## Reusable Pythonista client toolkit

A lightweight client module is provided at [`app/pythonista_client.py`](app/pythonista_client.py).

Key capabilities:

- Upload zip bytes or files
- Poll for completion
- Fetch tail logs
- Cancel or delete jobs
- Download and extract result zips
- Run an end-to-end submit, wait, and collect flow

A runnable example script is included at [`examples/pythonista_run_job.py`](examples/pythonista_run_job.py).

## HTTP API reference

All endpoints are served by the add-on.

### Public endpoints

- `GET /health` returns `{"status": "ok", "version": "<add-on version>"}`.
- `GET /` and `GET /index.html` return JSON info by default. If the client prefers HTML, they return the Web UI and require authentication.
- `GET /info.json` returns the same JSON info as `/`.

### Authenticated endpoints

Send the token in this header:

- `X-Runner-Token: <access token>`

Endpoints:

- `POST /run`: submit a job zip as raw bytes in the request body.
- `GET /jobs.json`: list jobs.
- `GET /package_profiles.json`: list discovered package profiles, default selection, and ready status.
- `GET /setup/status.json`: fetch guided setup readiness, blockers, warnings, and next steps for profile-mode examples.
- `GET /packages/cache.json`: fetch private package cache and storage summary.
- `GET /job/<job_id>.json`: fetch job status.
- `GET /tail/<job_id>.json`: fetch status plus stdout and stderr tails.
- `GET /result/<job_id>.zip`: download the result zip.
- `GET /stdout/<job_id>.txt`: download full stdout, or use offsets.
- `GET /stderr/<job_id>.txt`: download full stderr, or use offsets.
- `POST /cancel/<job_id>`: request cancellation.
- `DELETE /job/<job_id>`: delete a job and its artefacts.
- `POST /purge`: purge matching jobs.
- `POST /package_profiles/build`: build or rebuild one named package profile from JSON such as `{ "profile": "data_tools_basic", "rebuild": true }`.
- `POST /setup/upload-wheel`: upload one wheel file as raw bytes, with the filename supplied in `X-Upload-Filename` or the query string.
- `POST /setup/upload-profile-zip`: upload one profile archive as raw bytes, with the filename supplied in `X-Upload-Filename` or the query string.
- `POST /setup/delete-wheel`: delete one uploaded wheel using JSON such as `{ "filename": "demo_pkg-0.1.0-py3-none-any.whl" }`.
- `POST /setup/delete-profile`: delete one uploaded profile using JSON such as `{ "profile": "demo_formatsize_profile" }`.
- `POST /packages/cache/prune`: prune private package storage to the configured target.
- `POST /packages/cache/purge`: purge private package cache areas, with optional flags to also remove reusable virtual environments and imported wheels.

The full route contract is in [`api/openapi.json`](api/openapi.json).

## Pythonista client examples

Pythonista includes the `requests` module and a `dialogs` module for picking files.

### Example 1: submit a zip file you already built

```python
import requests

RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"
REQUEST_TIMEOUT_SECONDS = 60

with open("job.zip", "rb") as f:
    response = requests.post(
        RUNNER_URL + "/run",
        data=f,
        headers={
            "X-Runner-Token": TOKEN,
            "Content-Type": "application/zip",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

response.raise_for_status()
print(response.json())
```

### Example 2: use the reusable client helper

See [`app/pythonista_client.py`](app/pythonista_client.py) and [`examples/pythonista_run_job.py`](examples/pythonista_run_job.py).

## Release readiness and upgrade validation

The package subsystem is now implemented across cache reuse, offline wheelhouse imports, reusable virtual environments, named package profiles, Home Assistant entities, and package examples. Release readiness still depends on one final layer of validation that has to happen on real Home Assistant hosts, not just repository tests.

Use [`../docs/RELEASE_READINESS.md`](../docs/RELEASE_READINESS.md) as the live sign-off sheet for:

- regression runs across the core and package examples
- upgrade testing from earlier `0.6.13` installs that only knew the `_deps` model
- backup and restore checks for `/config/package_profiles/` and `/config/wheel_uploads/`
- native-host smoke testing on `aarch64` and `armv7`
- release notes and changelog completion

The add-on should now degrade cleanly when package features are disabled. The expected fallback is the older job-local dependency path or, when dependency handling is fully disabled, a normal `run.py` job with no package attachment. If your release candidate does not meet that behaviour on a real host, treat it as a blocker before cutting a stable tag.

## Troubleshooting

### `401 unauthorised`

Check all three of these:

1. **Access token** is set in the add-on configuration.
2. The request sends the correct `X-Runner-Token`.
3. **Ingress only** is off when you are calling the direct API.

### Pythonista cannot connect

Check that:

- The add-on is started.
- Your iPhone can reach the Home Assistant host on the local network.
- Port `8787` is not blocked by local firewall rules.
- Any CIDR allowlist includes your current client IP range.

### Upload fails immediately

Your zip must contain `run.py` at the zip root, not inside an extra parent folder.

### Result zip is missing your files

Only files written under `outputs/` are copied into the result zip.

### The Web UI loads but seems broken on mobile

Confirm you are on the latest add-on version, then hard refresh the Ingress page or restart the add-on so Home Assistant serves the current bundled `webui.html`.

## Security and operating notes

- Jobs run inside the add-on container, not on your iPhone.
- Direct API access and Ingress access are separate trust paths.
- Prefer Ingress for day-to-day human use.
- Keep direct API exposure local and token-protected.
- Review [`config.yaml`](config.yaml) before changing bind or security options.

## Packaging and architecture notes

The add-on declares support for `amd64`, `aarch64`, and `armv7` in [`config.yaml`](config.yaml), with matching build-matrix entries in [`build.yaml`](build.yaml).

Repository truthfulness note: automated runtime tests in this repository execute on `amd64` CI runners. `aarch64` and `armv7` are validated here at packaging and declaration level and still need native-host smoke testing before release sign-off.

## Advanced and contributor notes

- Repository landing page: [`../README.md`](../README.md)
- Security guidance: [`../SECURITY.md`](../SECURITY.md)
- Release channels: [`../docs/RELEASE_CHANNELS.md`](../docs/RELEASE_CHANNELS.md)
- Contributor guide: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- Web UI bundler: [`app/webui_build.py`](app/webui_build.py)
