# Version: 0.6.13-live-logs-tests.1
"""Tests for live subprocess output handling."""

from __future__ import annotations

import io
import os
import threading
import time

from runner.executor import _read_pipe_chunk


def test_read_pipe_chunk_returns_before_pipe_close() -> None:
    """Reading from a buffered pipe should return once bytes are available."""

    read_fd, write_fd = os.pipe()
    reader = io.BufferedReader(os.fdopen(read_fd, "rb", buffering=0))

    def _writer() -> None:
        try:
            time.sleep(0.05)
            os.write(write_fd, b"live\n")
            time.sleep(0.2)
        finally:
            os.close(write_fd)

    thread = threading.Thread(target=_writer, daemon=True)
    thread.start()

    started = time.monotonic()
    chunk = _read_pipe_chunk(reader, 8192)
    elapsed = time.monotonic() - started

    reader.close()
    thread.join(timeout=1)

    assert chunk == b"live\n"
    assert elapsed < 0.2
