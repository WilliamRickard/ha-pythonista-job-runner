Version: 0.6.13-examples.7

# Validation evidence for Example 05

This folder captures the first user validation run of `05_requirements_optional` using the standalone Pythonista runner.

## What is included

- `submitted.sanitised.json`: the submission metadata saved by the Pythonista runner
- `status.sanitised.json`: the final job status
- `download_attempts.sanitised.json`: the runner's download-attempt log for this run

## What this proves

This run proves the failure path with requirements installation disabled. The add-on returned `state: error` with `exit_code: 1`, which is the expected direction for the disabled-requirements path.

## Important limitation of this evidence

This run used runner script version `0.6.13-examples-runner.5`, which skipped result archive download for terminal `error` states. So this evidence does not include `result.zip` or extracted failure artefacts even though the add-on reported a result filename.

A rerun with the updated runner is still needed to capture:
- the failure-path result bundle
- the success-path result bundle with requirements installation enabled
