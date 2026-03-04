# Version: 0.6.12-refactor.2
"""Internal state containers for Runner.

This module centralises mutable job registry structures (jobs, ordering, and
process handles) so Runner can expose a stable compatibility surface while the
implementation evolves.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Any, Dict, List


@dataclass
class JobRegistry:
    """Mutable job registry shared across runner modules.

    The registry is intentionally small: it contains only the core mutable
    objects that historically lived as Runner instance attributes and are
    directly accessed by the test suite.
    """

    lock: threading.Lock
    jobs: Dict[str, Any]
    job_order: List[str]
    procs: Dict[str, Any]


def create_job_registry() -> JobRegistry:
    """Create a new, empty JobRegistry instance."""

    return JobRegistry(lock=threading.Lock(), jobs={}, job_order=[], procs={})
