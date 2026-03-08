"""Notification dispatch and throttling for job lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from homeassistant.core import HomeAssistant

from .const import NOTIFY_POLICY_ALL, NOTIFY_POLICY_FAILURES_ONLY


@dataclass
class NotificationManager:
    """Dispatch conservative notifications for meaningful job lifecycle transitions."""

    hass: HomeAssistant
    policy: str
    target: str
    throttle_seconds: int
    _last_sent: dict[str, datetime] = field(default_factory=dict)

    async def maybe_notify(self, event_key: str, title: str, message: str) -> None:
        """Notify when policy allows and throttle window has elapsed."""
        if self.policy == "off":
            return
        now = datetime.now(timezone.utc)
        prev = self._last_sent.get(event_key)
        if prev and (now - prev) < timedelta(seconds=max(0, self.throttle_seconds)):
            return

        if self.target.strip():
            domain, _, service = self.target.strip().partition(".")
            if domain and service:
                await self.hass.services.async_call(domain, service, {"title": title, "message": message}, blocking=False)
            else:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {"title": title, "message": message},
                    blocking=False,
                )
        else:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {"title": title, "message": message},
                blocking=False,
            )
        self._last_sent[event_key] = now

    async def handle_job_finished(self, *, job_id: str, state: str, exit_code: int | None) -> None:
        """Handle completion/failure notifications from coordinator transitions."""
        if state == "error" and self.policy in {NOTIFY_POLICY_FAILURES_ONLY, NOTIFY_POLICY_ALL}:
            await self.maybe_notify(
                "job_failed",
                "Pythonista Job Runner: job failed",
                f"Job {job_id} failed (exit_code={exit_code!s}).",
            )
            return
        if state == "done" and self.policy == NOTIFY_POLICY_ALL:
            await self.maybe_notify(
                "job_done",
                "Pythonista Job Runner: job completed",
                f"Job {job_id} completed successfully.",
            )
