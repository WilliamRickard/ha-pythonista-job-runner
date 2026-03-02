from __future__ import annotations

import hmac
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from runner_core import ADDON_VERSION, INGRESS_PROXY_IP, Runner, read_options
from utils import ip_in_cidrs, read_file_delta, stream_file
from webui import html_page


class RunnerHTTPServer(ThreadingHTTPServer):
    """HTTP server that carries a Runner instance for request handlers."""

    runner: Runner


class Handler(BaseHTTPRequestHandler):
    """HTTP API surface for the Runner.

    This is intentionally lightweight and dependency-free to remain usable in
    constrained environments (for example Pythonista).
    """

    server: RunnerHTTPServer

    def _write_bytes(self, data: bytes) -> None:
        """Write response bytes, swallowing client disconnects."""
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _drain_request_body(self, nbytes: int, max_drain: int = 16 * 1024 * 1024) -> None:
        """Read and discard request bytes to avoid client-side BrokenPipe errors.

        For very large bodies, we cap draining to avoid wasting too much time.
        """
        try:
            n = int(nbytes)
        except Exception:
            return
        if n <= 0:
            return
        if n > max_drain:
            # Too large to sensibly drain; leave it and let the connection close.
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
        """Send a JSON response with compact encoding."""
        b = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        self._send_bytes(code, "application/json; charset=utf-8", b)

    def _info_payload(self) -> dict[str, Any]:
        """Return a simple service index payload.

        This is useful for humans (quickly seeing what the service is) and for
        clients that want to discover the API surface without hard-coding.
        """

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

        # Ingress: trusted.
        if self._is_ingress():
            return True

        # Direct access: token plus optional CIDR allowlist.
        tok = self.headers.get("X-Runner-Token", "")
        if not runner.token or not hmac.compare_digest(tok, runner.token):
            return False

        cidrs = runner.api_allow_cidrs
        if cidrs:
            return ip_in_cidrs(self._get_client_ip(), list(cidrs))
        return True

    def _job_id_from_suffix(self, prefix: str, suffix: str) -> str:
        """Extract job_id from /<prefix>/<job_id><suffix> paths."""
        path = urlparse(self.path).path
        if not path.startswith(prefix):
            return ""
        if suffix and not path.endswith(suffix):
            return ""

        tail = path[len(prefix) :]
        if suffix:
            tail = tail[: -len(suffix)]
        tail = tail.strip("/")
        if not tail:
            return ""

        # Only allow a single path segment as job_id.
        # Take the last non-empty segment to avoid matching extra path parts.
        segments = [seg for seg in tail.split("/") if seg]
        if not segments:
            return ""
        job_id = segments[-1]

        # Reject suspicious or traversal-like job_ids.
        if job_id in (".", "..") or "/" in job_id:
            return ""

        return job_id
    @staticmethod
    def _parse_int(value: str | None, default: int) -> int:
        """Parse an int value or return the default."""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path in {"/", "/index.html"}:
            # Content negotiation: browsers get the Web UI, API clients get JSON.
            # This keeps direct access friendly (curl defaults to */*), while
            # ensuring Home Assistant Ingress still loads the HTML UI.
            accept = (self.headers.get("Accept") or "").lower()
            wants_html = ("text/html" in accept) or ("application/xhtml+xml" in accept)

            if wants_html:
                if not self._auth_ok():
                    self._json(401, {"error": "unauthorised"})
                    return
                self._send_bytes(200, "text/html; charset=utf-8", html_page(ADDON_VERSION))
                return

            # JSON index is safe to expose without auth (it contains no secrets).
            self._json(200, self._info_payload())
            return

        if path == "/health":
            self._json(200, {"status": "ok", "version": ADDON_VERSION})
            return

        if path == "/info.json":
            self._json(200, self._info_payload())
            return

        if not self._auth_ok():
            self._json(401, {"error": "unauthorised"})
            return

        runner = self.server.runner

        if path == "/stats.json":
            self._json(200, runner.stats_dict())
            return

        if path == "/jobs.json":
            jobs = [j.status_dict() for j in runner.list_jobs()]
            self._json(200, {"jobs": jobs})
            return

        if path.startswith("/job/") and path.endswith(".json"):
            job_id = self._job_id_from_suffix("/job/", ".json")
            if not job_id:
                self._json(404, {"error": "unknown_job"})
                return
            j = runner.get(job_id)
            if not j:
                self._json(404, {"error": "unknown_job"})
                return
            self._json(200, j.status_dict())
            return

        if path.startswith("/tail/") and path.endswith(".json"):
            job_id = self._job_id_from_suffix("/tail/", ".json")
            if not job_id:
                self._json(404, {"error": "unknown_job"})
                return
            j = runner.get(job_id)
            if not j:
                self._json(404, {"error": "unknown_job"})
                return

            q = parse_qs(urlparse(self.path).query)
            stdout_from = self._parse_int((q.get("stdout_from") or [None])[0], -1)
            stderr_from = self._parse_int((q.get("stderr_from") or [None])[0], -1)

            max_bytes_default = runner.tail_chars * 2
            max_bytes = self._parse_int(
                (q.get("max_bytes") or [str(max_bytes_default)])[0],
                max_bytes_default,
            )
            if max_bytes <= 0:
                max_bytes = max_bytes_default
            if max_bytes > 1024 * 1024:
                max_bytes = 1024 * 1024

            if stdout_from >= 0 or stderr_from >= 0:
                if stdout_from < 0:
                    stdout_from = 0
                if stderr_from < 0:
                    stderr_from = 0

                # max_bytes is applied per stream.
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

            self._json(
                200,
                {
                    "status": j.status_dict(),
                    "tail": {"stdout": j.tail_stdout.get(), "stderr": j.tail_stderr.get()},
                },
            )
            return

        if path.startswith("/result/") and path.endswith(".zip"):
            job_id = self._job_id_from_suffix("/result/", ".zip")
            if not job_id:
                self._json(404, {"error": "unknown_job"})
                return
            j = runner.get(job_id)
            if not j:
                self._json(404, {"error": "unknown_job"})
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
            return

        if path.startswith("/stdout/") and path.endswith(".txt"):
            job_id = self._job_id_from_suffix("/stdout/", ".txt")
            if not job_id:
                self._json(404, {"error": "unknown_job"})
                return
            j = runner.get(job_id)
            if not j:
                self._json(404, {"error": "unknown_job"})
                return
            if not j.stdout_path.exists():
                self._json(404, {"error": "not_ready"})
                return
            size = j.stdout_path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                stream_file(j.stdout_path, self.wfile.write)
            except (BrokenPipeError, ConnectionResetError):
                return
            return

        if path.startswith("/stderr/") and path.endswith(".txt"):
            job_id = self._job_id_from_suffix("/stderr/", ".txt")
            if not job_id:
                self._json(404, {"error": "unknown_job"})
                return
            j = runner.get(job_id)
            if not j:
                self._json(404, {"error": "unknown_job"})
                return
            if not j.stderr_path.exists():
                self._json(404, {"error": "not_ready"})
                return
            size = j.stderr_path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                stream_file(j.stderr_path, self.wfile.write)
            except (BrokenPipeError, ConnectionResetError):
                return
            return

        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        runner = self.server.runner

        if path.startswith("/cancel/"):
            if not self._auth_ok():
                self._json(401, {"error": "unauthorised"})
                return
            job_id = self._job_id_from_suffix("/cancel/", "")
            ok = runner.cancel(job_id)
            self._json(200, {"ok": ok})
            return

        if path == "/purge":
            if not self._auth_ok():
                self._json(401, {"error": "unauthorised"})
                return

            cl = self.headers.get("Content-Length")
            ln = self._parse_int(cl, 0) if cl else 0

            # Purge payload is tiny JSON; cap it defensively.
            if ln < 0 or ln > 16 * 1024:
                self._json(413, {"error": "payload_too_large"})
                return

            body = self.rfile.read(ln) if ln > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8", errors="replace") or "{}")
            except Exception:
                payload = {}

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

            res = runner.purge(states=states, older_than_hours=older_hours_i, dry_run=dry_run)
            self._json(200, res)
            return

        if path != "/run":
            self._json(404, {"error": "not_found"})
            return

        if not self._auth_ok():
            self._json(401, {"error": "unauthorised"})
            return

        cl = self.headers.get("Content-Length")
        if not cl:
            self._json(411, {"error": "length_required"})
            return

        ln = self._parse_int(cl, -1)
        if ln <= 0:
            self._json(400, {"error": "bad_content_length"})
            return

        max_bytes = int(runner.max_upload_mb) * 1024 * 1024
        if ln > max_bytes:
            # Drain modest bodies so simple clients (http.client) do not hit BrokenPipe while sending.
            self._drain_request_body(ln)
            self._json(413, {"error": "upload_too_large"})
            return

        body = self.rfile.read(ln)
        if len(body) != ln:
            self._json(400, {"error": "incomplete_upload"})
            return

        try:
            j = runner.new_job(body, self.headers, self._get_client_ip())
        except Exception as e:
            # Avoid leaking internal details in errors. The server log still shows the exception.
            self.log_error("Error creating job: %r", e)

            err = str(e).strip()
            safe = "job_creation_failed"
            if isinstance(e, RuntimeError) and re.fullmatch(r"[a-z0-9_]+", err):
                safe = err

            self._json(400, {"error": safe})
            return

        self._json(
            202,
            {
                "job_id": j.job_id,
                "tail_url": f"/tail/{j.job_id}.json",
                "result_url": f"/result/{j.job_id}.zip",
                "jobs_url": "/jobs.json",
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        runner = self.server.runner

        if path.startswith("/job/"):
            if not self._auth_ok():
                self._json(401, {"error": "unauthorised"})
                return
            job_id = self._job_id_from_suffix("/job/", "")
            ok = runner.delete(job_id)
            self._json(200, {"ok": ok})
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
