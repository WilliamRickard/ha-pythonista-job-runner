Version: 0.6.13-examples.3

# Example 01 commentary

`01_hello_world` is the smallest job in the examples suite, but it is also the most important one. It is the contract test for the whole add-on.

## Why this example exists

This job proves the minimum shape of a valid upload. The archive only needs `run.py` at zip root. When the add-on unpacks the zip, it runs that script in an isolated working directory and then collects anything written under `outputs/` into the final result archive.

That means this example checks five things at once:

1. the job zip is built correctly
2. `run.py` executes successfully
3. stdout and stderr are captured
4. files written to `outputs/` are returned in the result archive
5. the Pythonista runner can submit the job and save the result locally

## What the job code does

The script deliberately stays tiny and deterministic.

It prints a start line to stdout, writes `outputs/hello.txt`, writes `outputs/details.json`, then prints a completion line. There are no network calls, no random values, and no dependency installs. That is why the stable subset of the result can be checked into the repository.

## Why there are two kinds of result files in this folder

There are two categories of output for a job like this.

The first category is deterministic. These files should be identical every time the example runs:

- `outputs/hello.txt`
- `outputs/details.json`
- `stdout.txt`
- `stderr.txt`

Those files live under `expected_result/`, and their hashes are recorded in `expected_result_manifest.json`.

The second category is runtime-specific. These files change every run because they include timestamps, job IDs, or environment details:

- `status.json`
- `summary.txt`
- `job.log`
- `result_manifest.json`

Those files are still useful, but they are evidence rather than reference files.

## What the validation evidence shows

The `validation_evidence/2026-03-10_pythonista_user_run/` folder records the first successful user-run of this example through the standalone Pythonista runner.

That evidence matters because this example uncovered two real bugs in the runner flow:

- a race where very fast jobs could finish before the result archive was ready to download
- a tail-parsing mismatch after the add-on moved to the nested `status`, `tail`, and `offsets` response structure

The saved evidence confirms both issues are now fixed for this example.

## How to read the evidence

Start with `validation_evidence/.../comparison_to_expected.json`. That tells you whether the deterministic files from the real run match the checked-in reference subset.

Then read `validation_evidence/.../status.sanitised.json` and `download_attempts.sanitised.json`. Those show the job finished with `state: done`, `exit_code: 0`, and that the runner saved `result.zip` successfully.

## Why this example is the regression test for the runner

Because the job is so small, it stresses the awkward case where the whole run completes almost immediately. That makes it the best first check for the Pythonista runner. If `01_hello_world` can be submitted, monitored, downloaded, and compared successfully, the basic end-to-end flow is working.

Later examples can be richer, but they should still start from the same expectations demonstrated here.
