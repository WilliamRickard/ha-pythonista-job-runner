Version: 9

# Pythonista Job Runner examples implementation workplan

## Phase status

Legend:
- not started
- implemented, awaiting user run
- implemented, partial user validation captured
- complete

Current status:
- Phase 1: complete
- Phase 2: implemented, partial user validation captured
- Phase 3: not started
- Phase 4: not started
- Phase 5: not started
- Phase 6: not started
- Phase 7: not started
- Phase 8: not started
- Phase 9: not started
- Phase 10: not started


## Phase 2 implementation notes

- Examples `02_live_logs_progress` to `05_requirements_optional` are now implemented.
- `02_live_logs_progress` emits deterministic stdout once per second, adds periodic stderr warnings, and writes `outputs/progress_summary.json` plus `outputs/progress_timeline.txt`.
- `03_process_input_files` now bundles `data/sample_readings.csv`, processes it with relative paths only, and writes deterministic `processed.csv`, `summary.md`, and `stats.json` outputs.
- `04_cancel_long_running_job` now emits heartbeat logs, persists partial progress on every loop, handles `SIGTERM` and `SIGINT`, and is intended to be cancelled from the Home Assistant Web UI after several seconds.
- `05_requirements_optional` now includes `requirements.txt` and uses the `humanize` package when available. If requirements installation is disabled, it writes clear failure artefacts before raising a clear runtime error.
- Deterministic reference artefacts are now checked in for examples 02 and 03 under `expected_result/`, `expected_result.zip`, and `expected_result_manifest.json`.
- The standalone Pythonista runner now writes a zipped copy of each saved run folder beside the folder itself, making it easier to share or attach complete run evidence.
- User validation evidence is now checked in for examples 02 to 05 under each example's `validation_evidence/2026-03-10_pythonista_user_run/` folder.
- Example 02 validated successfully. The add-on run finished with `state: done`, `exit_code: 0`, and the deterministic files matched the checked-in references.
- Example 03 validated successfully overall, but the user run exposed a newline mismatch in the earlier checked-in deterministic `processed.csv` reference. The reference and example code have now been corrected to use the Linux add-on output style consistently.
- Example 04 was exercised successfully to completion, not cancellation. That proves the long-running output path works, but the intended cancellation-path validation is still pending.
- Example 05 was exercised successfully for the failure path with requirements installation disabled. That validates the clean-failure direction, but the success path with requirements installation enabled is still pending.
- The standalone Pythonista runner previously skipped result bundle download for terminal `error` states. That limitation is now fixed so future failure-path and cancellation-path validation runs can capture `result.zip` when the add-on exposes one.
- Phase 2 cannot be marked complete yet. Remaining validation tasks are:
  - cancel example 04 from the Home Assistant Web UI after several heartbeat lines
  - rerun example 05 with requirements installation enabled
  - optionally rerun example 05 with requirements installation disabled using runner version `0.6.13-examples-runner.6` so the failure-path result bundle is captured too

## Phase 1 implementation notes learnt from user validation

- The Pythonista runner initially failed to save output for the very fast `01_hello_world` job.
- Root cause 1: a race where the job could reach `done` before `/result/<job_id>.zip` was ready to serve.
- Fix applied: retry result-download for a short window after terminal completion and save `download_attempts.json` in the run folder.
- Root cause 2: the add-on `GET /tail/<job_id>.json` payload now returns nested `status`, `tail`, and `offsets` objects, but the standalone Pythonista runner was still reading an older flat schema.
- Fix applied: update the standalone runner to support both the current nested tail contract and the older flat tail contract.
- User validation then succeeded with `01_hello_world` using the standalone Pythonista runner and an embedded example zip from the packaged runner bundle.
- Evidence from the successful user run is now checked into `pythonista_job_runner/examples/core/01_hello_world/validation_evidence/2026-03-10_pythonista_user_run/`.
- The evidence includes sanitised submission metadata, final status, download attempts, a sanitised result archive, extracted result files, and a deterministic-file hash comparison against `expected_result/`.
- The first successful validated run completed in 1 second on the add-on side, finished with `state: done`, `exit_code: 0`, and saved `result.zip` successfully on the first download attempt.
- Example `01_hello_world` now has both deterministic reference artefacts and real validation evidence, plus a detailed `COMMENTARY.md` explaining how the example works and why it is the runner regression test.

### Earlier Phase 1 notes

- The first validation attempt failed with `http_error:400:zip_missing_run_py`.
- Root cause: the runner previously allowed any zip to be selected, but it did not help the user if they picked the outer bundle zip or repo zip instead of a direct example `job.zip`.
- The runner was then strengthened so it can:
  - accept a direct example `job.zip`
  - accept the repo zip and let the user choose an embedded example `job.zip`
  - accept the top-level bundle zip and recursively discover embedded example `job.zip` files
- Example zip building now excludes `__pycache__` and `.pyc` files.
- Example validation now checks that every built `job.zip` contains `run.py` at archive root.
- Phase 2 should now implement examples 02 to 05. Example 01 is already real and can be used as the regression check for the Pythonista runner.

## Purpose

Create a structured examples suite for the `pythonista_job_runner` add-on covering:

- 5 core examples that should work on the default lightweight add-on image.
- 5 advanced toolchain examples that introduce richer Python project structure plus native-language execution.
- consistent documentation, packaging, tests, and screenshots so the examples are usable from both the Home Assistant Web UI and Pythonista.

This plan assumes the current repository baseline already contains `pythonista_job_runner/examples/pythonista_run_job.py` and no full multi-example structure yet.

## Outcome

At the end of this plan the repository should contain:

- a top-level examples index
- 10 example folders, each with source files, a built zip, and a README
- docs updates linking the examples from user-facing docs
- automated validation for example structure and zip build health
- a clean separation between examples that work on the default image and examples that require an expanded toolchain image

## Recommended target structure

~~~text
pythonista_job_runner/
  examples/
    README.md
    README_TEMPLATE.md
    manifest.json
    core/
      README.md
      01_hello_world/
        README.md
        COMMENTARY.md
        job_src/
        job.zip
        expected_result/
        expected_result.zip
        expected_result_manifest.json
        validation_evidence/
      02_live_logs_progress/
        README.md
        job_src/
        job.zip
      03_process_input_files/
        README.md
        job_src/
        job.zip
      04_cancel_long_running_job/
        README.md
        job_src/
        job.zip
      05_requirements_optional/
        README.md
        job_src/
        job.zip
    toolchain/
      README.md
      06_python_package_and_tests/
        README.md
        job_src/
        job.zip
      07_cpp_compile_and_run/
        README.md
        job_src/
        job.zip
      08_rust_cargo_cli/
        README.md
        job_src/
        job.zip
      09_polyglot_same_task_benchmark/
        README.md
        job_src/
        job.zip
      10_python_orchestrates_native_binary/
        README.md
        job_src/
        job.zip
    tools/
      README.md
      build_example_zips.py
      validate_examples.py
      manifest_schema.md
      pythonista_run_example_job.py
~~~

## Example set to implement

### Core examples

#### 01 hello world

Purpose:
- prove the minimal `run.py` plus `outputs/` contract
- give users a first run that finishes quickly

Deliverables:
- `run.py`
- `outputs/hello.txt`
- README with expected stdout, stderr, and result zip contents
- `COMMENTARY.md` with a detailed explanation of the example
- checked-in validation evidence from a successful user run

Acceptance criteria:
- job completes in under 10 seconds on typical Home Assistant hardware
- result zip contains the output file and expected logs
- standalone Pythonista runner can submit the job, save the result, and match the deterministic subset against `expected_result/`

#### 02 live logs progress

Purpose:
- verify stdout and stderr stream live during execution
- validate the Web UI log view on an in-progress job

Deliverables:
- `run.py` that emits one progress line per second
- final `outputs/progress_summary.json`
- README with a specific instruction to watch logs update live

Acceptance criteria:
- users can observe line-by-line log growth before job completion
- stdout and stderr both receive content during the run

#### 03 process input files

Purpose:
- show that job zips can contain bundled input data as well as code
- demonstrate multiple output artefacts

Deliverables:
- sample CSV or JSON input file
- `run.py` that reads input and writes:
  - `outputs/summary.md`
  - `outputs/processed.csv`
  - `outputs/stats.json`

Acceptance criteria:
- example handles bundled data files using relative paths only
- generated outputs are deterministic

#### 04 cancel long running job

Purpose:
- demonstrate cancellation workflow and job state transitions
- confirm useful partial logs remain available after cancellation

Deliverables:
- `run.py` with heartbeat logging over roughly 2 minutes
- clean termination handling where practical
- README instructing the user when to press Cancel

Acceptance criteria:
- job can be cancelled from the Web UI
- final job state and logs remain understandable

#### 05 requirements optional

Purpose:
- demonstrate per-job dependency installation for Python examples
- keep dependency install separate from the simplest examples

Deliverables:
- `requirements.txt`
- lightweight pure-Python dependency
- `run.py` that uses the installed package
- README that clearly states the extra setup and runtime expectations

Acceptance criteria:
- example fails cleanly when requirements install is disabled
- example succeeds when requirements install is enabled

### Toolchain examples

#### 06 python package and tests

Purpose:
- show a realistic small Python project layout with source and tests
- demonstrate that a job can act like a miniature development task

Deliverables:
- `src/` and `tests/`
- built-in `unittest` or similarly lightweight standard-library test path
- outputs:
  - `outputs/test_report.txt`
  - `outputs/results.json`
  - `outputs/summary.md`

Acceptance criteria:
- test output streams live
- final artefacts summarise pass and fail counts

#### 07 cpp compile and run

Purpose:
- prove native compilation and execution in a toolchain-enabled image
- keep the example small enough to be understandable

Deliverables:
- a tiny C++ command-line program
- `run.py` orchestration that compiles then runs it
- outputs:
  - `outputs/program_output.txt`
  - `outputs/build_log.txt`
  - `outputs/runtime_summary.json`

Acceptance criteria:
- compile and run steps are logged separately
- README clearly marks this as toolchain-image only

#### 08 rust cargo cli

Purpose:
- prove Cargo-based Rust job execution in a toolchain-enabled image
- provide a modern systems-language example alongside C++

Deliverables:
- a small Cargo project
- `run.py` orchestration to build and run it
- outputs:
  - `outputs/result.json`
  - `outputs/build_log.txt`
  - `outputs/runtime_summary.md`

Acceptance criteria:
- Cargo build output streams live
- README clearly marks this as toolchain-image only

#### 09 polyglot same task benchmark

Purpose:
- compare Python, C++, and Rust implementations of the same task
- demonstrate orchestration of multiple executables from one job

Deliverables:
- one shared input dataset
- Python implementation
- C++ implementation
- Rust implementation
- `run.py` that runs all three and writes:
  - `outputs/benchmark.md`
  - `outputs/timings.json`
  - `outputs/output_consistency.json`

Acceptance criteria:
- all implementations produce equivalent logical output
- benchmark artefacts are understandable without reading the source

#### 10 python orchestrates native binary

Purpose:
- show a realistic mixed-language pattern with Python as controller and native code as worker
- avoid the complexity of Python extension modules in the examples suite

Deliverables:
- Python orchestration script
- C++ or Rust worker program
- outputs:
  - `outputs/report.html`
  - `outputs/summary.md`
  - `outputs/native_result.json`

Acceptance criteria:
- Python clearly prepares inputs and consumes native outputs
- README explains the value of this pattern compared with embedding native code into Python directly

## Phase breakdown

### Phase 1 - scaffolding, runner flow, and example 01

Scope:
- create the full examples directory structure
- add build and validation tooling
- create the standalone Pythonista runner flow
- implement `01_hello_world`
- validate `01_hello_world` with a real user run and check in the evidence

Deliverables:
- top-level examples structure
- `manifest.json`
- `build_example_zips.py`
- `validate_examples.py`
- `pythonista_run_example_job.py`
- implemented `01_hello_world`
- checked-in validation evidence and commentary for `01_hello_world`

Status: complete

### Phase 2 - implement core examples 02 to 05

Scope:
- replace scaffold placeholders for examples 02 to 05 with real jobs
- add deterministic expected outputs where appropriate
- update docs and validation for the new examples

Deliverables:
- implemented `02_live_logs_progress`
- implemented `03_process_input_files`
- implemented `04_cancel_long_running_job`
- implemented `05_requirements_optional`
- updated examples index and manifest notes

Exit criteria:
- each of the four examples has a real `job_src/`, built `job.zip`, and README
- validation script passes for the updated examples
- at least one of examples 02 to 05 is ready for user-run validation in the next turn

### Phase 3 - docs pass for the core example set

Scope:
- improve documentation quality across examples 01 to 05
- add consistent walkthroughs, expected outputs, and troubleshooting
- link the examples from user-facing docs in the repo

Deliverables:
- refreshed per-example READMEs
- examples index improvements
- docs links from existing repo documentation

Exit criteria:
- a new user can find and run the core examples without guesswork

### Phase 4 - implement example 06 python package and tests

Scope:
- build the richer Python mini-project example
- ensure it still works on the default image

Deliverables:
- `06_python_package_and_tests` implementation
- tests and outputs for the example
- documentation and validation updates

Exit criteria:
- example 06 demonstrates a real small Python project, not just a single script

### Phase 5 - design and image strategy for toolchain examples

Scope:
- decide whether toolchain examples live behind a separate dev image, build flag, or branch
- document the required packages and image impact before implementing 07 to 10

Deliverables:
- design note or README update describing the toolchain approach
- any required repo scaffolding for a dev image or optional package set

Exit criteria:
- the toolchain path is defined clearly enough to implement 07 to 10 without rework

### Phase 6 - implement example 07 cpp compile and run

Scope:
- add the first native-language example
- keep it simple and well documented

Deliverables:
- `07_cpp_compile_and_run` implementation
- build and run orchestration
- outputs and docs

Exit criteria:
- example 07 compiles and runs cleanly on the chosen toolchain image

### Phase 7 - implement example 08 rust cargo cli

Scope:
- add the Rust Cargo example
- capture build output and runtime output clearly

Deliverables:
- `08_rust_cargo_cli` implementation
- outputs and docs

Exit criteria:
- example 08 builds and runs cleanly on the chosen toolchain image

### Phase 8 - implement example 09 polyglot same-task benchmark

Scope:
- add the comparative multi-language example
- keep the task small enough to be understandable

Deliverables:
- `09_polyglot_same_task_benchmark` implementation
- benchmark artefacts and docs

Exit criteria:
- outputs clearly show both timings and output consistency

### Phase 9 - implement example 10 python orchestrates native binary

Scope:
- add the mixed-language orchestration example
- produce a report-style output that shows why this pattern is useful

Deliverables:
- `10_python_orchestrates_native_binary` implementation
- report output and docs

Exit criteria:
- example 10 demonstrates a realistic Python-plus-native workflow

### Phase 10 - final review and polish

Scope:
- run a full pass across all 10 examples
- clean up naming, docs, consistency, and validation coverage
- make sure examples remain easy to discover from the main repo docs

Deliverables:
- final consistency pass across manifests, READMEs, and build tooling
- screenshots or screenshots plan where useful
- final tidy-up updates

Exit criteria:
- the examples suite feels like a coherent product rather than a loose folder of sample jobs
