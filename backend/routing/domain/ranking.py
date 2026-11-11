"""Route-level risk summaries and the recommendation order."""
from __future__ import annotations

from dataclasses import dataclass

from .risk import Risk


@dataclass(frozen=True)
class RouteStats:
    route_id: str
    duration_s: float
    miles_by_risk: dict[Risk, float]

    @property
    def total_miles(self) -> float:
        return sum(self.miles_by_risk.values())

    @property
    def avg_risk(self) -> float:
        """Mile-weighted mean risk on a 0 (Low) to 4 (No Travel) scale."""
        total = self.total_miles
        if total == 0:
            return 0.0
        return sum(level * miles for level, miles in self.miles_by_risk.items()) / total

    @property
    def max_risk(self) -> Risk:
        present = [lvl for lvl, miles in self.miles_by_risk.items() if miles > 0]
        return max(present, default=Risk.LOW)


def sort_key(stats: RouteStats) -> tuple:
    """Lexicographic preference from the brief, best first.

    1. Fewest Severe miles  2. Fewest High miles  3. Lowest average risk  4. Shortest time

    "No Travel" miles are ranked ahead of everything: a route you are not allowed to drive
    must never beat one you are, whatever its Severe/High mileage. Each figure is compared at
    a practical resolution (whole miles, 0.01 risk, whole minutes) so that sampling noise on
    near-identical routes does not decide the order before the later criteria get a say.
    """
    return (
        round(stats.miles_by_risk.get(Risk.NO_TRAVEL, 0.0)),
        round(stats.miles_by_risk.get(Risk.SEVERE, 0.0)),
        round(stats.miles_by_risk.get(Risk.HIGH, 0.0)),
        round(stats.avg_risk, 2),
        round(stats.duration_s / 60),
    )


def rank(stats: list[RouteStats]) -> list[RouteStats]:
    return sorted(stats, key=sort_key)


_MILE_CRITERIA = ("No Travel miles", "Severe miles", "High miles")


def _hours_minutes(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def explain(best: RouteStats, others: list[RouteStats], names: dict[str, str]) -> list[str]:
    """Plain-language reasons the best route won, for the UI."""
    reasons: list[str] = []
    if not others:
        return ["Only one route available"]

    best_key = sort_key(best)
    runner_up = others[0]
    runner_key = sort_key(runner_up)
    deciding = next((i for i, (a, b) in enumerate(zip(best_key, runner_key)) if a != b), None)

    if deciding is None:
        reasons.append("Weather risk and travel time are effectively identical across routes")
    else:
        name = names[runner_up.route_id]
        a, b = best_key[deciding], runner_key[deciding]
        if deciding <= 2:
            reasons.append(f"Fewest {_MILE_CRITERIA[deciding]}: {a} mi vs {b} mi on {name}")
        elif deciding == 3:
            reasons.append(f"Lowest average weather risk: {a:.2f} vs {b:.2f} on {name}")
        else:
            reasons.append(
                "Weather risk is equivalent across routes, so the quickest wins: "
                f"{_hours_minutes(a)} vs {_hours_minutes(b)} on {name}"
            )

    if best_key[0] > 0:
        reasons.append(
            f"Warning: every option includes about {best_key[0]} mi of No Travel conditions"
        )
    return reasons
