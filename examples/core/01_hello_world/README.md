Version: 0.6.13-examples.3

# 01_hello_world - Hello world

Status: implemented and user-validated.

## What this example demonstrates

This is the minimal first-run example. It proves the required `run.py` plus `outputs/` contract and gives you a deterministic result to compare against the checked-in reference artefacts in this folder.

## Compatibility

This example works on the default lightweight add-on image.

## Files included

- `job_src/run.py`
- `job.zip`
- `expected_result/`
- `expected_result.zip`
- `expected_result_manifest.json`
- `COMMENTARY.md`
- `validation_evidence/2026-03-10_pythonista_user_run/`

## Expected duration

Usually under 10 seconds. The first successful user validation run completed in 1 second on the add-on side.

## How to run from Home Assistant Web UI

Upload `job.zip`, start the job, then compare your saved result against `expected_result/`.

## How to run from Pythonista

Use `examples/tools/pythonista_run_example_job.py` and select this folder's `job.zip`.

## Expected logs and outputs

Stable files you should compare:

- `outputs/hello.txt`
- `outputs/details.json`
- `stdout.txt`
- `stderr.txt`

The full add-on result zip also contains run-specific metadata such as job ID and timestamps. Those files are intentionally not included in `expected_result.zip`, because they are not deterministic.

## Reference result

Use `expected_result/` for an extracted reference, or `expected_result.zip` for a zipped reference containing only the deterministic files listed above.

## Validation evidence

A successful end-to-end user run through the standalone Pythonista runner is checked in under `validation_evidence/2026-03-10_pythonista_user_run/`.

That folder contains:

- sanitised runner metadata from the real run
- a sanitised copy of the downloaded result archive
- extracted result files
- a hash comparison showing that the deterministic subset matched `expected_result/`

Read `COMMENTARY.md` for the detailed explanation of how this example works and why it is the runner regression test.

## Troubleshooting

If the job finishes in Home Assistant but the Pythonista runner does not save `result.zip`, update to the latest runner script. The latest script retries the result download for very fast jobs, understands the current nested `/tail/<job_id>.json` response format, and writes `download_attempts.json` into the run folder for debugging.
