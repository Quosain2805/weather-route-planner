from __future__ import annotations


class UpstreamError(Exception):
    """A third-party API (routing, weather, geocoding) failed or returned something unusable."""

    def __init__(self, service: str, message: str, status: int = 502):
        super().__init__(message)
        self.service = service
        self.message = message
        self.status = status


class NoRouteError(Exception):
    """The routing provider could not connect origin and destination by road."""
