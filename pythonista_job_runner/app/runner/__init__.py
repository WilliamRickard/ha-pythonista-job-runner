# Version: 0.6.12-refactor.1
"""Internal implementation modules for runner_core.

These modules exist to keep runner_core.py small and maintainable while
preserving the existing public API and test surface.

Import policy:
- runner_core may import from runner.*
- runner.* modules should not import runner_core at runtime
"""

from __future__ import annotations
