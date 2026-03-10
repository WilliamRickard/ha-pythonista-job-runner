Version: 0.6.13-examples.3

# Validation evidence for Example 01

This folder captures the first successful end-to-end user validation run of `01_hello_world` using the standalone Pythonista runner.

## What is included

- `submitted.sanitised.json`: the submission response saved by the Pythonista runner
- `status.sanitised.json`: the final job status saved by the Pythonista runner
- `download_attempts.sanitised.json`: the runner's result-download attempts log
- `result.zip`: a sanitised copy of the downloaded result archive
- `result_extracted/`: the extracted contents of the sanitised result archive
- `comparison_to_expected.json`: hash-by-hash comparison between the deterministic files from this validated run and the checked-in reference files under `../expected_result/`

## What this proves

This evidence shows that the standalone Pythonista runner can now:

- submit `job.zip`
- follow the current `/tail/<job_id>.json` contract
- detect terminal completion
- download `result.zip` for a very fast job
- save the result alongside the runner metadata in a tidy run folder

Local-device paths and the LAN IP address have been redacted where they were not needed for the repository record.
