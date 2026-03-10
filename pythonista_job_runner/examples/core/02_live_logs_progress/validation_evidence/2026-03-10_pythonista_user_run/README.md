Version: 0.6.13-examples.7

# Validation evidence for Example 02

This folder captures the first successful end-to-end user validation run of `02_live_logs_progress` using the standalone Pythonista runner.

## What is included

- `submitted.sanitised.json`: the submission metadata saved by the Pythonista runner
- `status.sanitised.json`: the final job status
- `download_attempts.sanitised.json`: the result-download attempts log
- `result.zip`: a sanitised copy of the downloaded result archive
- `result_extracted/`: the extracted contents of the sanitised result archive
- `comparison_to_expected.json`: a deterministic file-by-file comparison against `../expected_result/`

## What this proves

This evidence shows that live stdout and stderr streamed successfully, the runner downloaded the finished result bundle, and the deterministic files matched the checked-in reference artefacts.
