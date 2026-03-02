# Version: 0.1.0

"""Non-secret configuration."""

from dataclasses import dataclass


@dataclass
class GhKitConfig:
    """Configuration values for API access."""

    api_base: str = "https://api.github.com"
    api_version: str = "2022-11-28"
    user_agent: str = "GhKitPythonista/0.1.0"
