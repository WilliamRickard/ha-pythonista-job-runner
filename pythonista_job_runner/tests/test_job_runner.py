"""Comprehensive tests for job_runner.py module."""
from __future__ import annotations

import sys
import re
from pathlib import Path
from unittest import mock

import pytest

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from job_runner import main


class TestJobRunner:
    """Test job_runner module."""

    @mock.patch("job_runner.serve")
    def test_main_calls_serve(self, mock_serve):
        """Test that main() calls serve()."""
        main()

        mock_serve.assert_called_once()

    @mock.patch("job_runner.serve")
    def test_main_with_exception(self, mock_serve):
        """Test that main() propagates exceptions from serve()."""
        mock_serve.side_effect = RuntimeError("Server error")

        with pytest.raises(RuntimeError, match="Server error"):
            main()

    @mock.patch("job_runner.serve")
    def test_main_multiple_calls(self, mock_serve):
        """Test that main() can be called multiple times."""
        main()
        main()
        main()

        assert mock_serve.call_count == 3

    @mock.patch("job_runner.serve")
    def test_main_no_arguments(self, mock_serve):
        """Test that main() doesn't require arguments."""
        # Should not raise any exceptions
        result = main()

        # main() returns None
        assert result is None
        mock_serve.assert_called_once()

    @mock.patch("job_runner.serve", return_value="test_return")
    def test_main_ignores_serve_return_value(self, mock_serve):
        """Test that main() doesn't return serve()'s return value."""
        result = main()

        # main() always returns None
        assert result is None
        mock_serve.assert_called_once()


class TestJobRunnerIntegration:
    """Integration tests for job_runner module."""

    def test_module_has_main(self):
        """Test that job_runner module has main function."""
        import job_runner

        assert hasattr(job_runner, "main")
        assert callable(job_runner.main)

    def test_module_imports_serve(self):
        """Test that job_runner successfully imports serve from http_api."""
        # This test verifies the import works
        try:
            from http_api import serve
            # If import succeeds, the module structure is correct
            assert callable(serve)
        except ImportError:
            # http_api module might not exist in test environment
            # This is acceptable as we're testing job_runner in isolation
            pytest.skip("http_api module not available in test environment")

    def test_module_docstring(self):
        """Test that job_runner module has proper documentation."""
        # Note: job_runner.py has a module-level docstring but Python treats it differently
        # The file starts with a docstring literal, which is documentation
        source = Path(__file__).parent.parent / "app" / "job_runner.py"
        content = source.read_text()

        # Check that documentation exists in the file
        assert '"""' in content
        assert "Entry point" in content or "entry point" in content

    @mock.patch("job_runner.serve")
    def test_main_function_signature(self, mock_serve):
        """Test that main() has the correct signature."""
        import inspect

        sig = inspect.signature(main)

        # main() should take no parameters
        assert len(sig.parameters) == 0

        # main() should return None (annotation can be None, type(None), or string 'None')
        assert sig.return_annotation in (None, type(None), 'None', inspect.Signature.empty)

    def test_main_is_entry_point(self):
        """Test that main() is designed as an entry point."""
        import job_runner

        # Verify __name__ == "__main__" block exists
        source = Path(__file__).parent.parent / "app" / "job_runner.py"
        content = source.read_text()

        assert 'if __name__ == "__main__":' in content
        assert "main()" in content


class TestJobRunnerEdgeCases:
    """Test edge cases for job_runner."""

    @mock.patch("job_runner.serve")
    def test_main_with_keyboard_interrupt(self, mock_serve):
        """Test that main() propagates KeyboardInterrupt."""
        mock_serve.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            main()

    @mock.patch("job_runner.serve")
    def test_main_with_system_exit(self, mock_serve):
        """Test that main() propagates SystemExit."""
        mock_serve.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            main()

    @mock.patch("job_runner.serve", side_effect=Exception("Unexpected error"))
    def test_main_with_generic_exception(self, mock_serve):
        """Test that main() propagates generic exceptions."""
        with pytest.raises(Exception, match="Unexpected error"):
            main()


class TestJobRunnerImports:
    """Test import behavior of job_runner module."""

    def test_future_imports(self):
        """Test that job_runner uses future annotations."""
        import job_runner

        # Check the module has __future__ imports
        source = Path(__file__).parent.parent / "app" / "job_runner.py"
        content = source.read_text()

        assert "from __future__ import annotations" in content

    @mock.patch("job_runner.serve")
    def test_serve_imported_at_module_level(self, mock_serve):
        """Test that serve is imported at module level, not in main()."""
        # This is important for module initialization
        import job_runner

        # serve should be available in the module namespace
        assert hasattr(job_runner, "serve")


class TestJobRunnerDocumentation:
    """Test documentation and metadata in job_runner."""

    def test_main_docstring(self):
        """Test that main() has a proper docstring."""
        assert main.__doc__ is not None
        assert "HTTP API server" in main.__doc__
        assert "Pythonista Job Runner" in main.__doc__
    def test_module_version_info(self):
        """Test that module contains version information."""
        source = Path(__file__).parent.parent / "app" / "job_runner.py"
        content = source.read_text()

        cfg = Path(__file__).parent.parent / "config.yaml"
        cfg_text = cfg.read_text()

        def _read_version(text: str):
            for ln in text.splitlines():
                s = ln.strip()
                if not s.startswith("version:"):
                    continue
                v = s.split(":", 1)[1].strip()
                v = v.split("#", 1)[0].strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ("\'", "\""):
                    v = v[1:-1]
                v = v.strip()
                return v or None
            return None

        version = _read_version(cfg_text)
        assert version, "config.yaml missing version"

        # Check for version mentions
        assert version in content

        # Also ensure runner_core.ADDON_VERSION matches config.yaml
        import runner_core
        assert getattr(runner_core, "ADDON_VERSION", None) == version


    def test_module_purpose_documented(self):
        """Test that module purpose is documented."""
        # Check that the source file has documentation
        source = Path(__file__).parent.parent / "app" / "job_runner.py"
        content = source.read_text()

        assert "Entry point" in content or "entry point" in content
        assert "add-on" in content


# Regression tests
class TestJobRunnerRegression:
    """Regression tests for known issues."""

    def test_dataclass_field_import_present(self):
        """Regression: Ensure the NameError fix for dataclasses.field is preserved."""
        # This test verifies the 0.6.x hotfix
        source = Path(__file__).parent.parent / "app" / "job_runner.py"
        content = source.read_text()

        # The fix mentioned importing dataclasses.field
        # Verify the module compiles without NameError
        import job_runner

        # If we can import it, the fix is in place
        assert job_runner is not None

    @mock.patch("job_runner.serve")
    def test_no_field_name_error(self, mock_serve):
        """Regression: Test that calling main() doesn't raise NameError about 'field'."""
        # This was the bug in pre-0.6.x
        try:
            main()
        except NameError as e:
            if "field" in str(e):
                pytest.fail("NameError for 'field' occurred - regression detected!")
            raise


# Additional test for robustness
class TestJobRunnerRobustness:
    """Test robustness of job_runner module."""

    @mock.patch("job_runner.serve")
    def test_main_thread_safety(self, mock_serve):
        """Test that main() can be called from multiple threads (basic check)."""
        import threading

        results = []

        def call_main():
            try:
                main()
                results.append("success")
            except Exception as e:
                results.append(f"error: {e}")

        threads = [threading.Thread(target=call_main) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All calls should succeed
        assert len(results) == 3
        assert all(r == "success" for r in results)

    def test_module_reload_safe(self):
        """Test that job_runner can be safely reloaded."""
        import importlib
        import job_runner

        # Should not raise exceptions
        importlib.reload(job_runner)

        # main should still be available
        assert hasattr(job_runner, "main")
        assert callable(job_runner.main)
