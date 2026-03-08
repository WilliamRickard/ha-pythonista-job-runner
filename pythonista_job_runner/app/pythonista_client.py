from __future__ import annotations

"""Reusable Pythonista-oriented client toolkit for the direct job runner API."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from utils import SafeZipLimits, safe_extract_zip_bytes


class RunnerClientError(RuntimeError):
    """Raised when the direct API returns an error or is unreachable."""


@dataclass(frozen=True)
class SubmittedJob:
    """Result from submitting a job to the runner."""

    job_id: str
    tail_url: str
    result_url: str
    jobs_url: str


@dataclass(frozen=True)
class JobExecutionResult:
    """Result bundle from running a job and downloading output artefacts."""

    submitted: SubmittedJob
    status: dict[str, Any]
    result_zip_path: Path
    extracted_to: Optional[Path]


class RunnerClient:
    """Small dependency-light direct API client suitable for Pythonista scripts."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

    def submit_zip_bytes(self, zip_bytes: bytes, *, content_type: str = "application/zip") -> SubmittedJob:
        """Upload raw zip bytes and return server-provided job links."""
        payload = self._request_json(
            "POST",
            "/run",
            data=zip_bytes,
            headers={"Content-Type": content_type, "Content-Length": str(len(zip_bytes))},
            expected_statuses={202},
        )
        return SubmittedJob(
            job_id=str(payload["job_id"]),
            tail_url=str(payload["tail_url"]),
            result_url=str(payload["result_url"]),
            jobs_url=str(payload["jobs_url"]),
        )

    def submit_zip_file(self, zip_path: Path | str) -> SubmittedJob:
        """Upload a zip file from disk."""
        path = Path(zip_path)
        return self.submit_zip_bytes(path.read_bytes())

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Return job status payload."""
        return self._request_json("GET", f"/job/{job_id}.json")

    def get_tail(
        self,
        job_id: str,
        *,
        stdout_from: Optional[int] = None,
        stderr_from: Optional[int] = None,
        max_bytes: Optional[int] = None,
    ) -> dict[str, Any]:
        """Fetch status + tail logs, optionally using byte offsets."""
        query: dict[str, int] = {}
        if stdout_from is not None:
            query["stdout_from"] = int(stdout_from)
        if stderr_from is not None:
            query["stderr_from"] = int(stderr_from)
        if max_bytes is not None:
            query["max_bytes"] = int(max_bytes)
        suffix = f"?{urlencode(query)}" if query else ""
        return self._request_json("GET", f"/tail/{job_id}.json{suffix}")

    def cancel_job(self, job_id: str) -> bool:
        """Request cancellation for a queued/running job."""
        payload = self._request_json("POST", f"/cancel/{job_id}")
        return bool(payload.get("ok", False))

    def delete_job(self, job_id: str) -> bool:
        """Request deletion of a job and its artefacts."""
        payload = self._request_json("DELETE", f"/job/{job_id}")
        return bool(payload.get("ok", False))

    def wait_for_completion(
        self,
        job_id: str,
        *,
        timeout_seconds: float = 600.0,
        terminal_states: Iterable[str] = ("done", "error"),
    ) -> dict[str, Any]:
        """Poll job status until completion or timeout."""
        deadline = time.time() + timeout_seconds
        allowed = set(terminal_states)
        last_status: dict[str, Any] | None = None

        while time.time() < deadline:
            last_status = self.get_job(job_id)
            if str(last_status.get("state")) in allowed:
                return last_status
            time.sleep(self.poll_interval_seconds)

        raise RunnerClientError(f"timed_out_waiting_for_job: {job_id}")

    def download_result_zip(self, job_id: str, dest_zip_path: Path | str) -> Path:
        """Download result zip for a completed job."""
        data = self._request_bytes("GET", f"/result/{job_id}.zip")
        out = Path(dest_zip_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return out

    @staticmethod
    def extract_result_zip(
        zip_path: Path | str,
        out_dir: Path | str,
        *,
        limits: SafeZipLimits | None = None,
    ) -> Path:
        """Extract a result zip to an output directory using safe extraction limits."""
        zip_file = Path(zip_path)
        dst = Path(out_dir)
        safe_extract_zip_bytes(zip_file.read_bytes(), dst, limits or SafeZipLimits())
        return dst

    def run_zip_and_collect(
        self,
        zip_path: Path | str,
        *,
        timeout_seconds: float = 600.0,
        result_zip_path: Path | str = Path("result.zip"),
        extract_to: Path | str | None = Path("result_extracted"),
    ) -> JobExecutionResult:
        """Submit, wait, download result zip, and optionally extract it."""
        submitted = self.submit_zip_file(zip_path)
        status = self.wait_for_completion(submitted.job_id, timeout_seconds=timeout_seconds)

        if status.get("state") != "done":
            err = status.get("error")
            raise RunnerClientError(f"job_failed: {submitted.job_id}: {err}")

        zip_out = self.download_result_zip(submitted.job_id, result_zip_path)
        extracted_path: Optional[Path] = None
        if extract_to is not None:
            extracted_path = self.extract_result_zip(zip_out, extract_to)

        return JobExecutionResult(
            submitted=submitted,
            status=status,
            result_zip_path=zip_out,
            extracted_to=extracted_path,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        payload = self._request_bytes(method, path, data=data, headers=headers, expected_statuses=expected_statuses)
        try:
            return json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RunnerClientError(f"invalid_json_response: {path}") from exc

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> bytes:
        url = f"{self.base_url}{path}"
        req_headers = {"X-Runner-Token": self.token}
        if headers:
            req_headers.update(headers)

        req = Request(url=url, data=data, headers=req_headers, method=method)
        ok_statuses = expected_statuses or {200}

        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:  # noqa: S310
                status = int(resp.status)
                body = resp.read()
        except HTTPError as exc:
            body = exc.read()
            detail = self._decode_error_body(body)
            raise RunnerClientError(f"http_error:{exc.code}:{detail}") from exc
        except URLError as exc:
            raise RunnerClientError(f"network_error:{exc.reason}") from exc

        if status not in ok_statuses:
            detail = self._decode_error_body(body)
            raise RunnerClientError(f"unexpected_status:{status}:{detail}")

        return body

    @staticmethod
    def _decode_error_body(body: bytes) -> str:
        if not body:
            return ""
        try:
            payload = json.loads(body.decode("utf-8"))
            err = payload.get("error")
            if isinstance(err, str):
                return err
        except Exception:
            pass
        try:
            return body.decode("utf-8", errors="replace")[:200]
        except Exception:
            return ""
