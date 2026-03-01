from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from runner_core import ADDON_VERSION, INGRESS_PROXY_IP, Runner, read_options
from utils import ip_in_cidrs, read_file_delta, stream_file
from webui import html_page


class Handler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    def _send_bytes(self, code: int, content_type: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj: Any) -> None:
        b = json.dumps(obj).encode("utf-8")
        self._send_bytes(code, "application/json; charset=utf-8", b)

    def _get_client_ip(self) -> str:
        try:
            return (self.client_address[0] or "").strip()
        except Exception:
            return ""

    def _is_ingress(self) -> bool:
        return self._get_client_ip() == INGRESS_PROXY_IP

    def _auth_ok(self) -> bool:
        runner: Runner = self.server.runner  # type: ignore[attr-defined]
        if runner.ingress_strict and not self._is_ingress():
            return False

        path = urlparse(self.path).path
        if path == "/health":
            return True

        # Ingress: trusted
        if self._is_ingress():
            return True

        # Direct access: token + optional CIDR allowlist
        tok = self.headers.get("X-Runner-Token", "")
        if not (runner.token and tok == runner.token):
            return False

        cidrs = runner.api_allow_cidrs
        if cidrs:
            return ip_in_cidrs(self._get_client_ip(), list(cidrs))
        return True

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path in {"/", "/index.html"}:
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorised"})
            return self._send_bytes(200, "text/html; charset=utf-8", html_page(ADDON_VERSION))

        if path == "/health":
            return self._json(200, {"status": "ok", "version": ADDON_VERSION})

        if path == "/info.json":
            return self._json(
                200,
                {
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
                    },
                },
            )

        if not self._auth_ok():
            return self._json(401, {"error": "unauthorised"})

        runner: Runner = self.server.runner  # type: ignore[attr-defined]

        if path == "/stats.json":
            return self._json(200, runner.stats_dict())

        if path == "/jobs.json":
            jobs = [j.status_dict() for j in runner.list_jobs()]
            return self._json(200, {"jobs": jobs})

        if path.startswith("/job/") and path.endswith(".json"):
            job_id = path.split("/")[-1][:-5]
            j = runner.get(job_id)
            if not j:
                return self._json(404, {"error": "unknown_job"})
            return self._json(200, j.status_dict())

        if path.startswith("/tail/") and path.endswith(".json"):
            job_id = path.split("/")[-1][:-5]
            j = runner.get(job_id)
            if not j:
                return self._json(404, {"error": "unknown_job"})

            q = parse_qs(urlparse(self.path).query)
            try:
                stdout_from = int((q.get("stdout_from") or ["-1"])[0])
                stderr_from = int((q.get("stderr_from") or ["-1"])[0])
            except Exception:
                stdout_from = -1
                stderr_from = -1
            try:
                max_bytes = int((q.get("max_bytes") or [str(runner.tail_chars * 2)])[0])
            except Exception:
                max_bytes = runner.tail_chars * 2
            if max_bytes <= 0:
                max_bytes = runner.tail_chars * 2
            if max_bytes > 1024 * 1024:
                max_bytes = 1024 * 1024

            if stdout_from >= 0 or stderr_from >= 0:
                if stdout_from < 0:
                    stdout_from = 0
                if stderr_from < 0:
                    stderr_from = 0
                out_txt, out_next, out_size = read_file_delta(j.stdout_path, stdout_from, max_bytes)
                err_txt, err_next, err_size = read_file_delta(j.stderr_path, stderr_from, max_bytes)
                return self._json(
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

            return self._json(200, {"status": j.status_dict(), "tail": {"stdout": j.tail_stdout.get(), "stderr": j.tail_stderr.get()}})

        if path.startswith("/result/") and path.endswith(".zip"):
            job_id = path.split("/")[-1][:-4]
            j = runner.get(job_id)
            if not j:
                return self._json(404, {"error": "unknown_job"})
            if not j.result_zip.exists():
                return self._json(404, {"error": "result_not_ready"})

            size = j.result_zip.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            stream_file(j.result_zip, self.wfile.write)
            return

        if path.startswith("/stdout/") and path.endswith(".txt"):
            job_id = path.split("/")[-1][:-4]
            j = runner.get(job_id)
            if not j:
                return self._json(404, {"error": "unknown_job"})
            if not j.stdout_path.exists():
                return self._json(404, {"error": "not_ready"})
            size = j.stdout_path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            stream_file(j.stdout_path, self.wfile.write)
            return

        if path.startswith("/stderr/") and path.endswith(".txt"):
            job_id = path.split("/")[-1][:-4]
            j = runner.get(job_id)
            if not j:
                return self._json(404, {"error": "unknown_job"})
            if not j.stderr_path.exists():
                return self._json(404, {"error": "not_ready"})
            size = j.stderr_path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            stream_file(j.stderr_path, self.wfile.write)
            return

        return self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        runner: Runner = self.server.runner  # type: ignore[attr-defined]

        if path.startswith("/cancel/"):
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorised"})
            job_id = path.split("/")[-1]
            ok = runner.cancel(job_id)
            return self._json(200, {"ok": ok})

        if path == "/purge":
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorised"})
            cl = self.headers.get("Content-Length")
            if not cl:
                ln = 0
            else:
                try:
                    ln = int(cl)
                except Exception:
                    return self._json(400, {"error": "bad_content_length"})
            # Purge payload is tiny JSON; cap it defensively
            if ln < 0 or ln > 16 * 1024:
                return self._json(413, {"error": "payload_too_large"})
            body = self.rfile.read(ln) if ln > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8", errors="replace") or "{}")
            except Exception:
                payload = {}
            states = payload.get("states") or []
            if isinstance(states, str):
                states = [states]
            if not isinstance(states, list):
                states = []
            older_hours = payload.get("older_than_hours")
            try:
                older_hours_i = int(older_hours) if older_hours is not None else 0
            except Exception:
                older_hours_i = 0
            dry_run = bool(payload.get("dry_run", False))
            res = runner.purge(states=states, older_than_hours=older_hours_i, dry_run=dry_run)
            return self._json(200, res)

        if path != "/run":
            return self._json(404, {"error": "not_found"})

        if not self._auth_ok():
            return self._json(401, {"error": "unauthorised"})

        cl = self.headers.get("Content-Length")
        if not cl:
            return self._json(411, {"error": "length_required"})
        try:
            ln = int(cl)
        except Exception:
            return self._json(400, {"error": "bad_content_length"})
        max_bytes = int(runner.max_upload_mb) * 1024 * 1024
        if ln <= 0:
            return self._json(400, {"error": "empty_upload"})
        if ln > max_bytes:
            return self._json(413, {"error": "upload_too_large"})

        body = self.rfile.read(ln)
        try:
            j = runner.new_job(body, self.headers, self._get_client_ip())
        except Exception as e:
            return self._json(400, {"error": f"{type(e).__name__}: {e}"})

        return self._json(
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
        runner: Runner = self.server.runner  # type: ignore[attr-defined]

        if path.startswith("/job/"):
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorised"})
            job_id = path.split("/")[-1]
            ok = runner.delete(job_id)
            return self._json(200, {"ok": ok})

        return self._json(404, {"error": "not_found"})


def serve() -> None:
    opts = read_options()
    runner = Runner(opts)
    httpd = ThreadingHTTPServer((runner.bind_host, runner.bind_port), Handler)
    httpd.runner = runner  # type: ignore[attr-defined]
    print(f"Runner listening on http://{runner.bind_host}:{runner.bind_port}", flush=True)
    httpd.serve_forever()

