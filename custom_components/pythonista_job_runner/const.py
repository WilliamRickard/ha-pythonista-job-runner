# Version: 0.3.0-const.1
"""Constants for Pythonista Job Runner integration."""

from __future__ import annotations

DOMAIN = "pythonista_job_runner"

CONF_BASE_URL = "base_url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CREATE_REPAIRS = "create_repairs"
CONF_NOTIFY_POLICY = "notify_policy"
CONF_NOTIFY_TARGET = "notify_target"
CONF_NOTIFY_THROTTLE_SECONDS = "notify_throttle_seconds"

DEFAULT_BASE_URL = "http://homeassistant.local:8787"
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_NOTIFY_POLICY = "failures_only"
DEFAULT_NOTIFY_TARGET = ""
DEFAULT_NOTIFY_THROTTLE_SECONDS = 600

NOTIFY_POLICY_OFF = "off"
NOTIFY_POLICY_FAILURES_ONLY = "failures_only"
NOTIFY_POLICY_ALL = "all"

EVENT_JOB_UPDATED = "pythonista_job_runner.job_updated"
EVENT_JOB_FINISHED = "pythonista_job_runner.job_finished"
EVENT_JOB_STARTED = "pythonista_job_runner.job_started"
EVENT_JOB_COMPLETED = "pythonista_job_runner.job_completed"
EVENT_JOB_FAILED = "pythonista_job_runner.job_failed"
EVENT_QUEUE_EMPTIED = "pythonista_job_runner.queue_emptied"

ISSUE_UNREACHABLE = "endpoint_unreachable"
ISSUE_AUTH = "auth_failed"

SERVICE_PURGE_JOBS = "purge_jobs"
SERVICE_PURGE_DONE_JOBS = "purge_done_jobs"
SERVICE_PURGE_FAILED_JOBS = "purge_failed_jobs"
SERVICE_REFRESH = "refresh"
SERVICE_CANCEL_JOB = "cancel_job"
SERVICE_BUILD_PACKAGE_PROFILE = "build_package_profile"
SERVICE_PRUNE_PACKAGE_CACHE = "prune_package_cache"
SERVICE_PURGE_PACKAGE_CACHE = "purge_package_cache"

RUNTIME_OPTION_KEYS = {
    CONF_SCAN_INTERVAL,
    CONF_CREATE_REPAIRS,
    CONF_NOTIFY_POLICY,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_THROTTLE_SECONDS,
}
