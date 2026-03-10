Version: 0.6.13-examples.7

# Validation evidence for Example 04

This folder captures the first user validation run of `04_cancel_long_running_job` using the standalone Pythonista runner.

## What is included

- `submitted.sanitised.json`: the submission metadata saved by the Pythonista runner
- `status.sanitised.json`: the final job status
- `download_attempts.sanitised.json`: the result-download attempts log
- `result.zip`: a sanitised copy of the downloaded result archive
- `result_extracted/`: the extracted contents of the sanitised result archive

## What this proves

This run proves the long-running example can execute successfully to completion and that the runner can save the larger result bundle afterwards.

## What it does not prove yet

This example is intended to validate cancellation. The attached run was allowed to complete normally, so the cancellation path still needs a separate user validation run from the Home Assistant Web UI.
