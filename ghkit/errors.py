# Version: 0.1.0

"""Error types for ghkit."""

class GhKitError(Exception):
    """Base error for ghkit."""


class GhKitHttpError(GhKitError):
    """Raised for HTTP-layer failures."""

    def __init__(self, message: str, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status
