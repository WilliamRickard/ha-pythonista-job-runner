"""Constants for Pythonista Job Runner integration."""

from __future__ import annotations

DOMAIN = "pythonista_job_runner"
PLATFORMS = ["sensor"]

CONF_BASE_URL = "base_url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CREATE_REPAIRS = "create_repairs"

DEFAULT_BASE_URL = "http://homeassistant.local:8787"
DEFAULT_SCAN_INTERVAL = 15

ISSUE_UNREACHABLE = "endpoint_unreachable"
ISSUE_AUTH = "auth_failed"
