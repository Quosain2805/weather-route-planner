"""One shared HTTP session with sane timeouts and a retry on transient failures."""
from __future__ import annotations

import time

import requests
from django.conf import settings

from .errors import UpstreamError

_session = requests.Session()
_session.headers.update({"User-Agent": settings.OUTBOUND_USER_AGENT})

RETRYABLE = {500, 502, 503, 504}


def get_json(service: str, url: str, params: dict | None = None, timeout: float = 20, retries: int = 1):
    last_error = "no response"
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        else:
            if resp.status_code == 429:
                raise UpstreamError(service, f"{service} is rate limiting us; try again shortly", 503)
            if resp.status_code in RETRYABLE:
                last_error = f"HTTP {resp.status_code}"
            elif resp.status_code >= 400:
                # 4xx bodies are meaningful to callers (e.g. OSRM's "NoRoute"), so hand them back.
                try:
                    return resp.json()
                except ValueError:
                    raise UpstreamError(service, f"{service} returned HTTP {resp.status_code}")
            else:
                try:
                    return resp.json()
                except ValueError:
                    raise UpstreamError(service, f"{service} returned invalid JSON")
        if attempt < retries:
            time.sleep(0.6 * (attempt + 1))
    raise UpstreamError(service, f"{service} is unavailable ({last_error})")
