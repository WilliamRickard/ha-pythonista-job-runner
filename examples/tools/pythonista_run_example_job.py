# Version: 0.6.13-examples-runner.6
"""Standalone Pythonista runner for Pythonista Job Runner example zips."""

from __future__ import annotations

import io
import json
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    import console  # type: ignore
except ImportError:  # pragma: no cover - Pythonista only
    console = None

try:
    import dialogs  # type: ignore
except ImportError:  # pragma: no cover - Pythonista only
    dialogs = None

try:
    import editor  # type: ignore
except ImportError:  # pragma: no cover - Pythonista only
    editor = None

try:
    import keychain  # type: ignore
except ImportError:  # pragma: no cover - Pythonista only
    keychain = None

KEYCHAIN_SERVICE = "pythonista_job_runner_examples"
KEYCHAIN_ACCOUNT_TOKEN = "runner_token"
KEYCHAIN_ACCOUNT_HOST = "home_assistant_host"
DEFAULT_PORT = 8787
REQUEST_TIMEOUT_SECONDS = 30.0
JOB_TIMEOUT_SECONDS = 900.0
POLL_INTERVAL_SECONDS = 1.0
RESULT_POLL_TIMEOUT_SECONDS = 20.0
RESULT_RETRYABLE_HTTP_CODES = {404, 409, 423, 425, 429, 500, 502, 503, 504}
RESULT_RETRY_SLEEP_SECONDS = 0.5


class RunnerClientError(RuntimeError):
    """Raised when the direct API returns an error or is unreachable."""


@dataclass(frozen=True)
class SubmittedJob:
    """Server response returned immediately after upload."""

    job_id: str
    tail_url: str
    result_url: str
    jobs_url: str


@dataclass(frozen=True)
class ResolvedJobZip:
    """Concrete job zip path ready to upload, plus selection metadata."""

    zip_path: Path
    selection_label: str
    source_path: Path
    was_embedded: bool


@dataclass(frozen=True)
class JobRunArtifacts:
    """Local output paths created by the runner script."""

    run_dir: Path
    selected_job_zip_path: Path
    result_zip_path: Optional[Path]
    status_json_path: Path
    submitted_json_path: Path
    extracted_dir: Optional[Path]
    download_attempts_path: Path
    run_bundle_zip_path: Path


class RunnerClient:
    """Minimal direct API client suitable for Pythonista scripts."""

    def __init__(self, base_url: str, token: str) -> None:
        """Store the base URL and token for later requests."""
        self.base_url = base_url.rstrip("/")
        self.token = token

    def submit_zip_file(self, zip_path: Path) -> SubmittedJob:
        """Upload a zip file and return the submitted job details."""
        payload = self._request_json(
            "POST",
            "/run",
            data=zip_path.read_bytes(),
            headers={
                "Content-Type": "application/zip",
                "Content-Length": str(zip_path.stat().st_size),
            },
            expected_statuses={202},
        )
        return SubmittedJob(
            job_id=str(payload["job_id"]),
            tail_url=str(payload["tail_url"]),
            result_url=str(payload["result_url"]),
            jobs_url=str(payload["jobs_url"]),
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Return the current job status payload."""
        return self._request_json("GET", f"/job/{job_id}.json")

    def get_tail(
        self,
        job_id: str,
        *,
        stdout_from: Optional[int] = None,
        stderr_from: Optional[int] = None,
        max_bytes: Optional[int] = None,
    ) -> dict[str, Any]:
        """Return the incremental stdout and stderr tails for a job."""
        query: dict[str, int] = {}
        if stdout_from is not None:
            query["stdout_from"] = int(stdout_from)
        if stderr_from is not None:
            query["stderr_from"] = int(stderr_from)
        if max_bytes is not None:
            query["max_bytes"] = int(max_bytes)
        suffix = f"?{urlencode(query)}" if query else ""
        return self._request_json("GET", f"/tail/{job_id}.json{suffix}")

    def download_result_zip(self, job_id: str, dest_zip_path: Path) -> Path:
        """Download the completed result zip for a job."""
        data = self._request_bytes("GET", f"/result/{job_id}.zip")
        dest_zip_path.parent.mkdir(parents=True, exist_ok=True)
        dest_zip_path.write_bytes(data)
        return dest_zip_path

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        """Perform an HTTP request and decode the JSON response body."""
        payload = self._request_bytes(
            method,
            path,
            data=data,
            headers=headers,
            expected_statuses=expected_statuses,
        )
        try:
            return json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RunnerClientError(f"invalid_json_response:{path}") from exc

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> bytes:
        """Perform an HTTP request and return the raw response bytes."""
        url = f"{self.base_url}{path}"
        req_headers = {"X-Runner-Token": self.token}
        if headers:
            req_headers.update(headers)
        req = Request(url=url, data=data, headers=req_headers, method=method)
        ok_statuses = expected_statuses or {200}
        try:
            with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
                status = int(response.status)
                body = response.read()
        except HTTPError as exc:
            detail = _decode_error_body(exc.read())
            raise RunnerClientError(f"http_error:{exc.code}:{detail}") from exc
        except URLError as exc:
            raise RunnerClientError(f"network_error:{exc.reason}") from exc

        if status not in ok_statuses:
            detail = _decode_error_body(body)
            raise RunnerClientError(f"unexpected_status:{status}:{detail}")
        return body


def _decode_error_body(body: bytes) -> str:
    """Best-effort decode for JSON or text error bodies."""
    if not body:
        return ""
    try:
        payload = json.loads(body.decode("utf-8"))
        detail = payload.get("error")
        if isinstance(detail, str):
            return detail
    except Exception:
        pass
    return body.decode("utf-8", errors="replace")[:200]


def _script_base_dir() -> Path:
    """Return the directory that contains this script, or the current directory."""
    if editor is not None:
        editor_path = editor.get_path()
        if editor_path:
            return Path(editor_path).resolve().parent
    return Path.cwd().resolve()


def _normalise_host(raw_value: str) -> str:
    """Normalise a host string into the direct API base URL."""
    value = raw_value.strip()
    if not value:
        raise RunnerClientError("home_assistant_host_required")
    value = value.replace("http://", "").replace("https://", "")
    value = value.rstrip("/")
    if ":" in value and value.rsplit(":", 1)[-1].isdigit():
        return f"http://{value}"
    return f"http://{value}:{DEFAULT_PORT}"


def _ensure_keychain_value(account: str, prompt_title: str, prompt_message: str, *, is_password: bool = False) -> str:
    """Load a value from the keychain or prompt the user and save it."""
    if keychain is not None:
        existing = keychain.get_password(KEYCHAIN_SERVICE, account)
        if existing:
            return existing

    entered = _prompt_for_value(prompt_title, prompt_message, is_password=is_password)
    if keychain is not None:
        keychain.set_password(KEYCHAIN_SERVICE, account, entered)
    return entered


def _prompt_for_value(title: str, message: str, *, is_password: bool = False) -> str:
    """Prompt the user for a value using Pythonista dialogs when available."""
    if dialogs is not None:
        field_type = "password" if is_password else "text"
        result = dialogs.form_dialog(
            title=title,
            fields=[
                {
                    "type": field_type,
                    "key": "value",
                    "title": title,
                    "placeholder": message,
                    "value": "",
                }
            ],
        )
        if not result or not str(result.get("value", "")).strip():
            raise RunnerClientError(f"{title.lower().replace(' ', '_')}_not_provided")
        return str(result["value"]).strip()

    entered = input(f"{title} ({message}): ").strip()
    if not entered:
        raise RunnerClientError(f"{title.lower().replace(' ', '_')}_not_provided")
    return entered


def _zip_bytes_has_root_run_py(data: bytes) -> bool:
    """Return True when zip bytes contain `run.py` at the archive root."""
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            names = {name.rstrip("/") for name in archive.namelist()}
    except zipfile.BadZipFile:
        return False
    return "run.py" in names


def _zip_file_has_root_run_py(path: Path) -> bool:
    """Return True when a zip file contains `run.py` at the archive root."""
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = {name.rstrip("/") for name in archive.namelist()}
    except zipfile.BadZipFile as exc:
        raise RunnerClientError(f"selected_zip_is_invalid:{path.name}") from exc
    return "run.py" in names


def _safe_label_fragment(value: str) -> str:
    """Return a filesystem-safe fragment derived from a member label."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "embedded_job"


def _discover_embedded_job_zips_from_bytes(
    data: bytes,
    *,
    origin_label: str,
    max_depth: int = 3,
    _depth: int = 0,
) -> list[tuple[str, bytes]]:
    """Return embedded job zips reachable within a selected bundle or repo zip."""
    if _depth >= max_depth:
        return []

    discovered: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            for member in archive.infolist():
                if member.is_dir() or not member.filename.lower().endswith(".zip"):
                    continue
                member_bytes = archive.read(member.filename)
                label = f"{origin_label} :: {member.filename}"
                if _zip_bytes_has_root_run_py(member_bytes):
                    discovered.append((label, member_bytes))
                    continue
                discovered.extend(
                    _discover_embedded_job_zips_from_bytes(
                        member_bytes,
                        origin_label=label,
                        max_depth=max_depth,
                        _depth=_depth + 1,
                    )
                )
    except zipfile.BadZipFile:
        return []

    deduped: list[tuple[str, bytes]] = []
    seen_labels: set[str] = set()
    for label, member_bytes in discovered:
        if label in seen_labels:
            continue
        deduped.append((label, member_bytes))
        seen_labels.add(label)
    return deduped


def _choose_embedded_job_zip(discovered: list[tuple[str, bytes]]) -> tuple[str, bytes]:
    """Prompt the user to choose one embedded job zip from a bundle or repo zip."""
    labels = [label for label, _ in discovered]
    selected_label: Optional[str] = None
    if dialogs is not None and hasattr(dialogs, "list_dialog"):
        selected_label = dialogs.list_dialog(title="Choose embedded job zip", items=labels)
    if not selected_label:
        for index, label in enumerate(labels, start=1):
            print(f"{index}. {label}")
        raw = input("Choose embedded job zip number: ").strip()
        if not raw.isdigit():
            raise RunnerClientError("embedded_job_zip_not_selected")
        selected_index = int(raw)
        if selected_index < 1 or selected_index > len(discovered):
            raise RunnerClientError("embedded_job_zip_not_selected")
        return discovered[selected_index - 1]
    for label, member_bytes in discovered:
        if label == selected_label:
            return label, member_bytes
    raise RunnerClientError("embedded_job_zip_not_selected")


def _resolve_selected_job_zip(selected_zip: Path, run_dir: Path) -> ResolvedJobZip:
    """Return a runnable job zip, extracting from bundle or repo zips when needed."""
    if _zip_file_has_root_run_py(selected_zip):
        staged_path = run_dir / f"selected_job_{selected_zip.name}"
        shutil.copyfile(selected_zip, staged_path)
        return ResolvedJobZip(
            zip_path=staged_path,
            selection_label=selected_zip.name,
            source_path=selected_zip,
            was_embedded=False,
        )

    discovered = _discover_embedded_job_zips_from_bytes(
        selected_zip.read_bytes(),
        origin_label=selected_zip.name,
    )
    if not discovered:
        raise RunnerClientError(
            "selected_zip_missing_root_run_py_and_contains_no_embedded_job_zip"
        )

    label, member_bytes = _choose_embedded_job_zip(discovered)
    extracted_name = f"selected_job_{_safe_label_fragment(label)}.zip"
    extracted_path = run_dir / extracted_name
    extracted_path.write_bytes(member_bytes)
    print(f"Resolved embedded job zip: {label}")
    print(f"Extracted embedded job zip to: {extracted_path}")
    return ResolvedJobZip(
        zip_path=extracted_path,
        selection_label=label,
        source_path=selected_zip,
        was_embedded=True,
    )


def _pick_zip_file() -> Path:
    """Open the iOS document picker and return the selected zip path."""
    if dialogs is not None:
        selected = dialogs.pick_document()
        if not selected:
            raise RunnerClientError("job_zip_not_selected")
        path = Path(selected)
    else:
        entered = input("Path to job zip: ").strip()
        if not entered:
            raise RunnerClientError("job_zip_not_selected")
        path = Path(entered)

    if path.suffix.lower() != ".zip":
        raise RunnerClientError("selected_file_is_not_a_zip")
    if not path.exists():
        raise RunnerClientError(f"selected_file_missing:{path}")
    return path


def _timestamp() -> str:
    """Return a local timestamp suitable for result folder names."""
    return time.strftime("%Y%m%d_%H%M%S")


def _create_run_dir(selected_zip: Path) -> Path:
    """Create the output folder for one runner invocation."""
    base_dir = _script_base_dir() / "runner_results"
    base_dir.mkdir(parents=True, exist_ok=True)
    run_dir = base_dir / f"{selected_zip.stem}_{_timestamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _extract_zip_safely(zip_path: Path, target_dir: Path) -> Path:
    """Extract the result zip while blocking path traversal."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RunnerClientError(f"unsafe_zip_member:{member.filename}")
            destination = (target_dir / member.filename).resolve()
            if not str(destination).startswith(str(target_root)):
                raise RunnerClientError(f"unsafe_zip_member:{member.filename}")
        archive.extractall(target_dir)
    return target_dir


def _write_json(path: Path, payload: Any) -> Path:
    """Write JSON with indentation and stable key order."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _zip_directory(source_dir: Path, destination_zip: Path) -> Path:
    """Zip a directory recursively, preserving the top-level folder name."""
    destination_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path == destination_zip:
                continue
            if path.is_dir():
                continue
            arcname = Path(source_dir.name) / path.relative_to(source_dir)
            archive.write(path, arcname.as_posix())
    return destination_zip


def _print_text_chunk(prefix: str, text: str) -> None:
    """Print a text chunk with an optional prefix per line."""
    for line in text.splitlines():
        if prefix:
            print(f"{prefix}{line}")
        else:
            print(line)


def _coerce_int(value: Any, default: int) -> int:
    """Return an integer value when possible, otherwise the supplied default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_tail_payload_fields(
    tail: dict[str, Any],
    *,
    stdout_offset: int,
    stderr_offset: int,
) -> tuple[str, str, int, int, str]:
    """Normalise old and new tail payload formats into one tuple."""
    if isinstance(tail.get("status"), dict):
        status = tail["status"]
        tail_section = tail.get("tail") or {}
        offsets = tail.get("offsets") or {}
        return (
            str(tail_section.get("stdout", "")),
            str(tail_section.get("stderr", "")),
            _coerce_int(offsets.get("stdout_next"), stdout_offset),
            _coerce_int(offsets.get("stderr_next"), stderr_offset),
            str(status.get("state") or ""),
        )
    return (
        str(tail.get("stdout_append", "")),
        str(tail.get("stderr_append", "")),
        _coerce_int(tail.get("stdout_offset"), stdout_offset),
        _coerce_int(tail.get("stderr_offset"), stderr_offset),
        str(tail.get("state") or ""),
    )


def _stream_job_until_terminal(client: RunnerClient, submitted: SubmittedJob) -> dict[str, Any]:
    """Poll status and live log tails until the job reaches a terminal state."""
    stdout_offset = 0
    stderr_offset = 0
    deadline = time.time() + JOB_TIMEOUT_SECONDS
    last_state: Optional[str] = None

    while time.time() < deadline:
        tail = client.get_tail(
            submitted.job_id,
            stdout_from=stdout_offset,
            stderr_from=stderr_offset,
            max_bytes=65536,
        )
        stdout_text, stderr_text, stdout_offset, stderr_offset, state = _extract_tail_payload_fields(
            tail,
            stdout_offset=stdout_offset,
            stderr_offset=stderr_offset,
        )

        if stdout_text:
            _print_text_chunk("", stdout_text)
        if stderr_text:
            _print_text_chunk("[stderr] ", stderr_text)

        if state and state != last_state:
            print(f"[state] {state}")
            last_state = state
        if state in {"done", "error", "cancelled", "canceled"}:
            if isinstance(tail.get("status"), dict):
                return dict(tail["status"])
            return client.get_job(submitted.job_id)
        time.sleep(POLL_INTERVAL_SECONDS)

    raise RunnerClientError(f"timed_out_waiting_for_job:{submitted.job_id}")


def _result_error_http_code(exc: RunnerClientError) -> Optional[int]:
    """Return the HTTP status code embedded in a runner client error, when present."""
    message = str(exc)
    if not message.startswith("http_error:"):
        return None
    parts = message.split(":", 2)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


def _is_retryable_result_download_error(exc: RunnerClientError) -> bool:
    """Return True when a result download failure should be retried briefly."""
    code = _result_error_http_code(exc)
    if code is None:
        return str(exc).startswith("network_error:")
    return code in RESULT_RETRYABLE_HTTP_CODES


def _download_result_zip_with_retries(
    client: RunnerClient,
    job_id: str,
    run_dir: Path,
) -> tuple[Path, Path]:
    """Retry result download briefly to avoid races on very fast jobs."""
    attempts: list[dict[str, Any]] = []
    attempts_path = run_dir / "download_attempts.json"
    deadline = time.time() + RESULT_POLL_TIMEOUT_SECONDS
    attempt_number = 0
    last_error: Optional[str] = None

    while time.time() <= deadline:
        attempt_number += 1
        started = time.time()
        try:
            result_zip_path = client.download_result_zip(job_id, run_dir / "result.zip")
        except RunnerClientError as exc:
            error_message = str(exc)
            retryable = _is_retryable_result_download_error(exc)
            attempts.append(
                {
                    "attempt": attempt_number,
                    "elapsed_seconds": round(time.time() - started, 3),
                    "result": "error",
                    "error": error_message,
                    "retryable": retryable,
                }
            )
            _write_json(attempts_path, attempts)
            if not retryable:
                raise
            last_error = error_message
            time.sleep(RESULT_RETRY_SLEEP_SECONDS)
            continue

        attempts.append(
            {
                "attempt": attempt_number,
                "elapsed_seconds": round(time.time() - started, 3),
                "result": "saved",
                "path": str(result_zip_path),
            }
        )
        _write_json(attempts_path, attempts)
        return result_zip_path, attempts_path

    _write_json(attempts_path, attempts)
    raise RunnerClientError(
        f"result_zip_not_available_after_retries:{job_id}:{last_error or 'no_result_from_server'}"
    )


def _maybe_download_terminal_result_zip(
    client: RunnerClient,
    job_id: str,
    run_dir: Path,
    *,
    terminal_state: str,
) -> tuple[Optional[Path], Optional[Path], Path]:
    """Try to download a result zip for any terminal state and extract it when present."""
    download_attempts_path = run_dir / "download_attempts.json"
    if terminal_state not in {"done", "error", "cancelled", "canceled"}:
        _write_json(
            download_attempts_path,
            [
                {
                    "attempt": 0,
                    "result": "skipped",
                    "reason": f"terminal_state:{terminal_state}",
                }
            ],
        )
        return None, None, download_attempts_path

    try:
        result_zip_path, download_attempts_path = _download_result_zip_with_retries(
            client,
            job_id,
            run_dir,
        )
    except RunnerClientError as exc:
        if terminal_state == "done":
            raise
        print(f"Result zip not available for terminal state {terminal_state}: {exc}")
        return None, None, download_attempts_path

    extracted_dir = _extract_zip_safely(result_zip_path, run_dir / "result_extracted")
    return result_zip_path, extracted_dir, download_attempts_path


def run_selected_zip() -> JobRunArtifacts:
    """Prompt for settings and a job zip, then submit the job and save artefacts."""
    host = _ensure_keychain_value(
        KEYCHAIN_ACCOUNT_HOST,
        "Home Assistant host",
        "Example: 192.168.1.10 or homeassistant.local",
    )
    token = _ensure_keychain_value(
        KEYCHAIN_ACCOUNT_TOKEN,
        "Runner token",
        "Paste the direct API runner token",
        is_password=True,
    )
    selected_zip = _pick_zip_file()
    base_url = _normalise_host(host)
    run_dir = _create_run_dir(selected_zip)
    print(f"Run folder: {run_dir}")
    resolved_zip = _resolve_selected_job_zip(selected_zip, run_dir)
    client = RunnerClient(base_url=base_url, token=token)

    print(f"Selected zip: {selected_zip}")
    if resolved_zip.was_embedded:
        print(f"Chosen embedded job zip: {resolved_zip.selection_label}")
    print(f"Upload job zip: {resolved_zip.zip_path}")
    print(f"Runner URL: {base_url}")
    print(f"Results folder: {run_dir}")

    submitted = client.submit_zip_file(resolved_zip.zip_path)
    submitted_json_path = _write_json(
        run_dir / "submitted.json",
        {
            "job_id": submitted.job_id,
            "jobs_url": submitted.jobs_url,
            "result_url": submitted.result_url,
            "selected_job_zip": str(resolved_zip.zip_path),
            "selected_job_zip_label": resolved_zip.selection_label,
            "selected_zip": str(selected_zip),
            "selected_zip_was_embedded": resolved_zip.was_embedded,
            "tail_url": submitted.tail_url,
        },
    )
    print(f"Submitted job: {submitted.job_id}")

    status = _stream_job_until_terminal(client, submitted)
    status_json_path = _write_json(run_dir / "status.json", status)

    terminal_state = str(status.get("state"))
    result_zip_path, extracted_dir, download_attempts_path = _maybe_download_terminal_result_zip(
        client,
        submitted.job_id,
        run_dir,
        terminal_state=terminal_state,
    )
    if result_zip_path is not None:
        print(f"Result zip saved to: {result_zip_path}")
    else:
        print(f"No result zip saved. Final state: {terminal_state}")
    if extracted_dir is not None:
        print(f"Result extracted to: {extracted_dir}")

    run_bundle_zip_path = _zip_directory(run_dir, run_dir.with_suffix(".zip"))
    print(f"Submitted JSON saved to: {submitted_json_path}")
    print(f"Status JSON saved to: {status_json_path}")
    print(f"Download attempts JSON saved to: {download_attempts_path}")
    print(f"Run folder zip saved to: {run_bundle_zip_path}")
    print(f"Run folder ready: {run_dir}")
    return JobRunArtifacts(
        run_dir=run_dir,
        selected_job_zip_path=resolved_zip.zip_path,
        result_zip_path=result_zip_path,
        status_json_path=status_json_path,
        submitted_json_path=submitted_json_path,
        extracted_dir=extracted_dir,
        download_attempts_path=download_attempts_path,
        run_bundle_zip_path=run_bundle_zip_path,
    )


def main() -> None:
    """Entry point for manual Pythonista use."""
    try:
        artefacts = run_selected_zip()
    except Exception as exc:
        if console is not None:
            console.hud_alert(str(exc), "error", 2.0)
        print(f"Runner failed: {exc}")
        print(f"Runner base folder: {_script_base_dir() / 'runner_results'}")
        return

    if console is not None:
        console.hud_alert("Job finished", "success", 1.5)
    print(f"Run folder ready: {artefacts.run_dir}")


if __name__ == "__main__":
    main()
