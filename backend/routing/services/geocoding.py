"""Place search for the origin/destination boxes.

Photon (OpenStreetMap data, built for search-as-you-type) is tried first and Nominatim is the
fallback, so one flaky public instance does not take the form down.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.cache import cache

from .errors import UpstreamError
from .http import get_json

log = logging.getLogger(__name__)

SERVICE = "Geocoding service"
LIMIT = 6


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


def search(query: str) -> list[dict]:
    query = " ".join(query.split())
    key = f"geo:v1:{query.lower()}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        places = _photon(query)
    except UpstreamError as exc:
        log.warning("Photon failed (%s); falling back to Nominatim", exc.message)
        places = _nominatim(query)

    out = [asdict(p) for p in places]
    cache.set(key, out, settings.GEOCODE_CACHE_TTL_S)
    return out


def _photon(query: str) -> list[Place]:
    data = get_json(SERVICE, settings.PHOTON_URL, {"q": query, "limit": LIMIT, "lang": "en"}, timeout=4, retries=0)
    places = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        lon, lat = feat["geometry"]["coordinates"][:2]
        parts = [
            props.get("name"),
            props.get("street") and f"{props.get('housenumber', '')} {props['street']}".strip(),
            props.get("city") if props.get("city") != props.get("name") else None,
            props.get("state"),
            props.get("country"),
        ]
        label = ", ".join(dict.fromkeys(p for p in parts if p))
        if label:
            places.append(Place(label, lat, lon))
    return places


def _nominatim(query: str) -> list[Place]:
    data = get_json(
        SERVICE,
        settings.NOMINATIM_URL,
        {"q": query, "format": "jsonv2", "limit": LIMIT},
        timeout=10,
    )
    if not isinstance(data, list):
        raise UpstreamError(SERVICE, "unexpected geocoding response")
    return [Place(item["display_name"], float(item["lat"]), float(item["lon"])) for item in data]
