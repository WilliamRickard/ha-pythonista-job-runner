from __future__ import annotations

"""HTTP API server and request handlers for job runner endpoints."""

import hmac
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from zipfile import BadZipFile

from runner_core import ADDON_VERSION, INGRESS_PROXY_IP, Runner, read_options
from utils import ip_in_cidrs, read_file_delta, stream_file
from webui import html_page


class RunnerHTTPServer(ThreadingHTTPServer):
    """HTTP server that carries a Runner instance for request handlers."""

    runner: Runner


class Handler(BaseHTTPRequestHandler):
    """HTTP API surface for the Runner."""

    server: RunnerHTTPServer

    def _write_bytes(self, data: bytes) -> None:
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _drain_request_body(self, nbytes: int, max_drain: int = 16 * 1024 * 1024) -> None:
        try:
            n = int(nbytes)
        except Exception:
            return
        if n <= 0 or n > max_drain:
            return
        remaining = n
        while remaining > 0:
            chunk = self.rfile.read(min(65536, remaining))
            if not chunk:
                break
            remaining -= len(chunk)

    def _send_bytes(self, code: int, content_type: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self._write_bytes(data)

    def _json(self, code: int, obj: Any) -> None:
        self._send_bytes(code, "application/json; charset=utf-8", json.dumps(obj, separators=(",", ":")).encode("utf-8"))

    @staticmethod
    def _parse_int(value: str | None, default: int) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _info_payload(self) -> dict[str, Any]:
        return {
            "service": "pythonista_job_runner",
            "version": ADDON_VERSION,
            "endpoints": {
                "health": "/health",
                "run": "POST /run",
                "tail": "/tail/<job_id>.json",
                "result": "/result/<job_id>.zip",
                "jobs": "/jobs.json",
                "job": "/job/<job_id>.json",
                "stdout": "/stdout/<job_id>.txt",
                "stderr": "/stderr/<job_id>.txt",
                "stats": "/stats.json",
                "purge": "POST /purge",
                "cancel": "POST /cancel/<job_id>",
                "delete": "DELETE /job/<job_id>",
            },
        }

    def _get_client_ip(self) -> str:
        try:
            return (self.client_address[0] or "").strip()
        except Exception:
            return ""

    def _is_ingress(self) -> bool:
        return self._get_client_ip() == INGRESS_PROXY_IP

    def _auth_ok(self) -> bool:
        runner = self.server.runner
        if runner.ingress_strict and not self._is_ingress():
            return False

        path = urlparse(self.path).path
        if path == "/health":
            return True
        if self._is_ingress():
            return True

        tok = self.headers.get("X-Runner-Token", "")
        if not runner.token or not hmac.compare_digest(tok, runner.token):
            return False

        cidrs = runner.api_allow_cidrs
        return ip_in_cidrs(self._get_client_ip(), list(cidrs)) if cidrs else True

    def _job_id_from_suffix(self, prefix: str, suffix: str) -> str:
        path = urlparse(self.path).path
        if not path.startswith(prefix) or (suffix and not path.endswith(suffix)):
            return ""
        tail = path[len(prefix) :]
        if suffix:
            tail = tail[: -len(suffix)]
        job_id = tail.strip("/")
        if not job_id or "/" in job_id or job_id in (".", ".."):
            return ""
        return job_id

    def _require_auth(self) -> bool:
        if self._auth_ok():
            return True
        self._json(401, {"error": "unauthorised"})
        return False

    def _get_job_or_404(self, prefix: str, suffix: str) -> Any | None:
        job_id = self._job_id_from_suffix(prefix, suffix)
        if not job_id:
            self._json(404, {"error": "unknown_job"})
            return None
        job = self.server.runner.get(job_id)
        if not job:
            self._json(404, {"error": "unknown_job"})
            return None
        return job

    def _send_text_delta_or_stream(self, file_path: Any, query: dict[str, list[str]], tail_chars: int) -> None:
        from_off = self._parse_int((query.get("from") or [None])[0], -1)
        max_bytes = self._parse_int((query.get("max_bytes") or [None])[0], 0)

        if from_off >= 0 or max_bytes > 0:
            from_off = max(0, from_off)
            max_bytes_default = tail_chars * 2
            if max_bytes <= 0:
                max_bytes = max_bytes_default
            max_bytes = min(max_bytes, 1024 * 1024)
            txt, next_off, size = read_file_delta(file_path, from_off, max_bytes)
            data = txt.encode("utf-8", errors="replace")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-File-Size", str(size))
            self.send_header("X-From-Offset", str(from_off))
            self.send_header("X-Next-Offset", str(next_off))
            self.end_headers()
            self._write_bytes(data)
            return

        size = file_path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            stream_file(file_path, self.wfile.write)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _handle_root_get(self, path: str) -> bool:
        if path not in {"/", "/index.html"}:
            return False
        accept = (self.headers.get("Accept") or "").lower()
        wants_html = ("text/html" in accept) or ("application/xhtml+xml" in accept)
        if wants_html:
            if not self._require_auth():
                return True
            self._send_bytes(200, "text/html; charset=utf-8", html_page(ADDON_VERSION))
            return True
        self._json(200, self._info_payload())
        return True

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if self._handle_root_get(path):
            return
        if path == "/health":
            self._json(200, {"status": "ok", "version": ADDON_VERSION})
            return
        if path == "/info.json":
            self._json(200, self._info_payload())
            return
        if not self._require_auth():
            return

        runner = self.server.runner
        if path == "/stats.json":
            self._json(200, runner.stats_dict())
            return
        if path == "/jobs.json":
            self._json(200, {"jobs": [j.status_dict() for j in runner.list_jobs()]})
            return
        if path.startswith("/job/") and path.endswith(".json"):
            j = self._get_job_or_404("/job/", ".json")
            if j:
                self._json(200, j.status_dict())
            return
        if path.startswith("/tail/") and path.endswith(".json"):
            self._handle_tail_get(runner)
            return
        if path.startswith("/result/") and path.endswith(".zip"):
            self._handle_result_get()
            return
        if path.startswith("/stdout/") and path.endswith(".txt"):
            self._handle_stream_get("/stdout/", ".txt", "stdout_path")
            return
        if path.startswith("/stderr/") and path.endswith(".txt"):
            self._handle_stream_get("/stderr/", ".txt", "stderr_path")
            return
        self._json(404, {"error": "not_found"})

    def _handle_tail_get(self, runner: Runner) -> None:
        j = self._get_job_or_404("/tail/", ".json")
        if not j:
            return
        q = parse_qs(urlparse(self.path).query)
        stdout_from = self._parse_int((q.get("stdout_from") or [None])[0], -1)
        stderr_from = self._parse_int((q.get("stderr_from") or [None])[0], -1)
        max_bytes_default = runner.tail_chars * 2
        max_bytes = self._parse_int((q.get("max_bytes") or [str(max_bytes_default)])[0], max_bytes_default)
        if max_bytes <= 0:
            max_bytes = max_bytes_default
        max_bytes = min(max_bytes, 1024 * 1024)

        if stdout_from >= 0 or stderr_from >= 0:
            stdout_from = max(0, stdout_from)
            stderr_from = max(0, stderr_from)
            out_txt, out_next, out_size = read_file_delta(j.stdout_path, stdout_from, max_bytes)
            err_txt, err_next, err_size = read_file_delta(j.stderr_path, stderr_from, max_bytes)
            self._json(
                200,
                {
                    "status": j.status_dict(),
                    "tail": {"stdout": out_txt, "stderr": err_txt},
                    "offsets": {
                        "stdout_from": stdout_from,
                        "stdout_next": out_next,
                        "stdout_size": out_size,
                        "stderr_from": stderr_from,
                        "stderr_next": err_next,
                        "stderr_size": err_size,
                    },
                },
            )
            return
        self._json(200, {"status": j.status_dict(), "tail": {"stdout": j.tail_stdout.get(), "stderr": j.tail_stderr.get()}})

    def _handle_result_get(self) -> None:
        j = self._get_job_or_404("/result/", ".zip")
        if not j:
            return
        if not j.result_zip.exists():
            self._json(404, {"error": "result_not_ready"})
            return
        size = j.result_zip.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            stream_file(j.result_zip, self.wfile.write)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _handle_stream_get(self, prefix: str, suffix: str, field_name: str) -> None:
        j = self._get_job_or_404(prefix, suffix)
        if not j:
            return
        file_path = getattr(j, field_name)
        if not file_path.exists():
            self._json(404, {"error": "not_ready"})
            return
        self._send_text_delta_or_stream(file_path, parse_qs(urlparse(self.path).query), self.server.runner.tail_chars)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/cancel/"):
            self._handle_cancel_post()
            return
        if path == "/purge":
            self._handle_purge_post()
            return
        if path == "/run":
            self._handle_run_post()
            return
        self._json(404, {"error": "not_found"})

    @staticmethod
    def _normalised_content_type(content_type_header: str | None) -> str:
        """Return a lower-cased media type without optional parameters."""
        return (content_type_header or "").split(";", 1)[0].strip().lower()

    def _validate_content_type(self, allowed_types: set[str], *, optional: bool = True) -> bool:
        """Validate request content type against an allowlist."""
        content_type = self._normalised_content_type(self.headers.get("Content-Type"))
        if not content_type and optional:
            return True
        if content_type in allowed_types:
            return True
        self._json(415, {"error": "unsupported_content_type"})
        return False

    @staticmethod
    def _safe_runtime_error_code(exc: RuntimeError) -> str:
        """Return a safe API error code derived from RuntimeError text."""
        err = str(exc).strip()
        primary = err.split(":", 1)[0].strip()
        if re.fullmatch(r"[a-z0-9_]+", primary):
            return primary
        return "job_creation_failed"

    def _handle_cancel_post(self) -> None:
        if not self._require_auth():
            return
        job_id = self._job_id_from_suffix("/cancel/", "")
        self._json(200, {"ok": self.server.runner.cancel(job_id)})

    def _handle_purge_post(self) -> None:
        if not self._require_auth():
            return
        cl = self.headers.get("Content-Length")
        ln = self._parse_int(cl, 0) if cl else 0
        if ln < 0 or ln > 16 * 1024:
            self._json(413, {"error": "payload_too_large"})
            return
        if not self._validate_content_type({"application/json", "text/json"}, optional=True):
            return

        body = self.rfile.read(ln) if ln > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8", errors="replace") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid_json"})
            return

        if not isinstance(payload, dict):
            self._json(400, {"error": "invalid_json"})
            return

        raw_states = payload.get("states")
        if raw_states is None:
            raw_states = payload.get("state")
        states: Any = raw_states or []
        if isinstance(states, str):
            states = [states]
        if not isinstance(states, list):
            states = []
        older_hours = payload.get("older_than_hours")
        older_hours_i = self._parse_int(str(older_hours) if older_hours is not None else None, 0)
        dry_run = bool(payload.get("dry_run", False))
        self._json(200, self.server.runner.purge(states=states, older_than_hours=older_hours_i, dry_run=dry_run))

    def _handle_run_post(self) -> None:
        if not self._require_auth():
            return
        if not self._validate_content_type({"application/zip", "application/octet-stream"}, optional=True):
            return

        cl = self.headers.get("Content-Length")
        if not cl:
            self._json(411, {"error": "length_required"})
            return
        ln = self._parse_int(cl, -1)
        if ln <= 0:
            self._json(400, {"error": "bad_content_length"})
            return
        runner = self.server.runner
        max_bytes = int(runner.max_upload_mb) * 1024 * 1024
        if ln > max_bytes:
            self._drain_request_body(ln)
            self._json(413, {"error": "upload_too_large"})
            return

        body = self.rfile.read(ln)
        if len(body) != ln:
            self._json(400, {"error": "incomplete_upload"})
            return

        try:
            j = runner.new_job(body, self.headers, self._get_client_ip())
        except BadZipFile:
            self._json(400, {"error": "invalid_zip"})
            return
        except RuntimeError as e:
            self.log_error("Error creating job: %r", e)
            self._json(400, {"error": self._safe_runtime_error_code(e)})
            return
        except (OSError, ValueError, TypeError) as e:
            self.log_error("Error creating job: %r", e)
            self._json(400, {"error": "job_creation_failed"})
            return

        self._json(202, {"job_id": j.job_id, "tail_url": f"/tail/{j.job_id}.json", "result_url": f"/result/{j.job_id}.zip", "jobs_url": "/jobs.json"})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/job/"):
            if not self._require_auth():
                return
            job_id = self._job_id_from_suffix("/job/", "")
            self._json(200, {"ok": self.server.runner.delete(job_id)})
            return
        self._json(404, {"error": "not_found"})


def serve() -> None:
    """Load options, create a Runner, and serve the HTTP API."""
    opts = read_options()
    runner = Runner(opts)
    httpd = RunnerHTTPServer((runner.bind_host, runner.bind_port), Handler)
    httpd.runner = runner
    print(f"Runner listening on http://{runner.bind_host}:{runner.bind_port}", flush=True)
    httpd.serve_forever()
