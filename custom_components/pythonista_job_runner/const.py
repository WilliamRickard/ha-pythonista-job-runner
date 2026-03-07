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

EVENT_JOB_UPDATED = "pythonista_job_runner.job_updated"
EVENT_JOB_FINISHED = "pythonista_job_runner.job_finished"

SERVICE_PURGE_JOBS = "purge_jobs"
SERVICE_PURGE_DONE_JOBS = "purge_done_jobs"
SERVICE_PURGE_FAILED_JOBS = "purge_failed_jobs"
SERVICE_REFRESH = "refresh"
SERVICE_CANCEL_JOB = "cancel_job"
