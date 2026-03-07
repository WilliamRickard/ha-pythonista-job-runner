"""Pythonista-ready example using the reusable RunnerClient toolkit.

Usage on Pythonista:
1) Copy this file and `app/pythonista_client.py` into your Pythonista scripts.
2) Edit RUNNER_URL and TOKEN.
3) Run the script.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from pythonista_client import RunnerClient, RunnerClientError

RUNNER_URL = "http://YOUR_HOME_ASSISTANT_HOST:8787"
TOKEN = "YOUR_RUNNER_TOKEN"


def _build_demo_zip(out_path: Path) -> Path:
    """Create a minimal job zip with run.py at archive root."""
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "run.py",
            """import os
print('hello from pythonista client toolkit')
os.makedirs('outputs', exist_ok=True)
with open('outputs/hello.txt', 'w', encoding='utf-8') as f:
    f.write('result from add-on\n')
""",
        )
    out_path.write_bytes(payload.getvalue())
    return out_path


def main() -> None:
    """Submit demo job and print resulting artefact paths."""
    zip_path = _build_demo_zip(Path("demo_job.zip"))
    client = RunnerClient(RUNNER_URL, TOKEN, timeout_seconds=60, poll_interval_seconds=1.0)

    try:
        result = client.run_zip_and_collect(
            zip_path,
            timeout_seconds=300,
            result_zip_path=Path("result.zip"),
            extract_to=Path("result_files"),
        )
    except RunnerClientError as exc:
        print(f"Job failed: {exc}")
        raise

    print("Job finished")
    print(f"Job ID: {result.submitted.job_id}")
    print(f"Result zip: {result.result_zip_path}")
    print(f"Extracted to: {result.extracted_to}")


if __name__ == "__main__":
    main()
