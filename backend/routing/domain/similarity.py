"""Deciding whether two candidate routes are genuinely different roads."""
from __future__ import annotations

from .path import Path

CELL_DEG = 0.01  # ~0.7 mi: GPS-level wobble between two traces of the same road falls in one cell


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return round(lat / CELL_DEG), round(lon / CELL_DEG)


def _samples(path: Path, spacing_mi: float) -> list[tuple[float, float]]:
    n = max(2, int(path.total_miles / spacing_mi) + 1)
    out = []
    for i in range(n + 1):
        p = path.at_mile(path.total_miles * i / n)
        out.append((p.lat, p.lon))
    return out


def overlap_fraction(candidate: Path, other: Path) -> float:
    """Share of `candidate` (0..1) that runs within about a mile of `other`."""
    other_cells = {_cell(lat, lon) for lat, lon in _samples(other, 0.5)}
    cand = _samples(candidate, 2.0)
    shared = 0
    for lat, lon in cand:
        cy, cx = _cell(lat, lon)
        if any((cy + dy, cx + dx) in other_cells for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
            shared += 1
    return shared / len(cand)
