<!-- Version: 0.6.14-docs.1 -->
# Pythonista Job Runner

Pythonista Job Runner is a Home Assistant add-on for the "phone as controller, Home Assistant as worker" workflow.

You create a small job zip on your iPhone, upload it from Pythonista, let Home Assistant run `run.py`, then download the result zip back to the phone.

This file stays short on purpose. The full user guide lives in [DOCS.md](DOCS.md).

## What it gives you

- A direct HTTP API for Pythonista and other scripts.
- An Ingress Web UI for jobs, logs, package cache, package profiles, setup uploads, and downloads inside Home Assistant.
- A predictable job contract built around `run.py` and `outputs/`.
- Result bundles that include logs, status files, and package diagnostics when dependency handling is active.
- A persistent package subsystem with pip cache reuse, offline wheelhouse imports, reusable virtual environments, and named package profiles.

## Fastest route to a first run

1. Install the add-on.
2. Set a strong **Access token**.
3. Start the add-on.
4. Open **Open Web UI** and confirm the jobs list loads.
5. Upload a tiny job zip from Pythonista.

If you want to use the direct API from Pythonista, keep **Ingress only** off. Setup detail, including the guided Setup flow for wheel and profile uploads in the Web UI, package-mode guidance, migration notes, and examples are in [DOCS.md](DOCS.md).

## Pick the right path

- Use the **Web UI** when you want the simplest human workflow inside Home Assistant.
- Use the **direct API** when Pythonista needs to submit jobs itself.
- Use **per-job mode** when the job carries its own dependency definition.
- Use **profile mode** when you want multiple jobs to share one named prepared package environment.

A concrete Pythonista example is in [DOCS.md](DOCS.md#first-run-from-pythonista).

## Architecture support

The add-on declares support for `amd64`, `aarch64`, and `armv7`, using Home Assistant base Python images configured in [`build.yaml`](build.yaml).

Repository truthfulness note: automated runtime tests in this repository currently run on `amd64` CI runners. `aarch64` and `armv7` are validated at packaging and declaration level here and still need native-host smoke testing before release sign-off.

## Read next

- [DOCS.md](DOCS.md) for installation, package modes, migration, Pythonista examples, troubleshooting, and API reference.
- [`examples/README.md`](examples/README.md) for the full examples catalogue.
- [`examples/packages/README.md`](examples/packages/README.md) for cache reuse, offline wheelhouse, and profile-mode examples.
- [`api/openapi.json`](api/openapi.json) for the machine-readable direct API contract.
- [`../docs/RELEASE_READINESS.md`](../docs/RELEASE_READINESS.md) for the release checklist, upgrade matrix, and manual sign-off record.
- [`app/pythonista_client.py`](app/pythonista_client.py) for the reusable client helper module.
- [`examples/pythonista_run_job.py`](examples/pythonista_run_job.py) for a runnable end-to-end example.
