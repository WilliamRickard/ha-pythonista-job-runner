"""Guardrail tests for add-on packaging, architecture, and security config alignment."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def _top_level_yaml_list_items(text: str, key: str) -> list[str]:
    """Return items from a simple top-level YAML list (`key:\n  - item`)."""
    lines = text.splitlines()
    items: list[str] = []
    in_section = False

    for line in lines:
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            in_section = (line.strip() == f"{key}:")
            continue
        if not in_section:
            continue
        if not line.startswith("  - "):
            if line and not line.startswith(" "):
                break
            continue
        items.append(line.split("-", 1)[1].strip())
    return items


def _top_level_yaml_map_keys(text: str, key: str) -> list[str]:
    """Return keys from a simple top-level YAML map (`key:\n  k: v`)."""
    lines = text.splitlines()
    keys: list[str] = []
    in_section = False

    for line in lines:
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            in_section = (line.strip() == f"{key}:")
            continue
        if not in_section:
            continue
        if line.startswith("  ") and ":" in line:
            k = line.strip().split(":", 1)[0]
            keys.append(k)
            continue
        if line and not line.startswith(" "):
            break
    return keys


def test_config_arch_and_build_from_are_aligned() -> None:
    config_text = _read("pythonista_job_runner/config.yaml")
    build_text = _read("pythonista_job_runner/build.yaml")

    config_arches = _top_level_yaml_list_items(config_text, "arch")
    build_arches = _top_level_yaml_map_keys(build_text, "build_from")

    assert config_arches, "config.yaml arch list must not be empty"
    assert set(config_arches) == set(build_arches)


def test_build_from_uses_home_assistant_arch_python_base_images() -> None:
    build_text = _read("pythonista_job_runner/build.yaml")
    build_arches = _top_level_yaml_map_keys(build_text, "build_from")

    for arch in build_arches:
        expected_prefix = f"  {arch}: ghcr.io/home-assistant/{arch}-base-python:"
        assert expected_prefix in build_text


def test_dockerfile_uses_supervisor_build_from_arg() -> None:
    dockerfile = _read("pythonista_job_runner/Dockerfile")

    assert "ARG BUILD_FROM" in dockerfile
    assert "FROM $BUILD_FROM" in dockerfile


def test_security_schema_keys_exist_for_direct_api_controls() -> None:
    config_text = _read("pythonista_job_runner/config.yaml")

    assert "token: password" in config_text
    assert "ingress_strict: bool" in config_text
    assert "api_allow_cidrs:" in config_text


def test_docs_note_supported_architectures() -> None:
    root_readme = _read("README.md")
    addon_readme = _read("pythonista_job_runner/README.md")

    for arch in ("amd64", "aarch64", "armv7"):
        assert f"`{arch}`" in root_readme
        assert f"`{arch}`" in addon_readme


def test_docs_include_architecture_validation_scope_note() -> None:
    root_readme = _read("README.md")
    docs = _read("pythonista_job_runner/DOCS.md")

    assert "automated test suite in this repository executes on `amd64` CI runners" in root_readme
    assert "automated runtime tests in this repository execute on `amd64` CI runners" in docs


def test_custom_apparmor_allows_supervisor_init_entrypoint() -> None:
    profile = _read("pythonista_job_runner/apparmor.txt")

    assert "/init rix," in profile
    assert "/run.sh rix," in profile
