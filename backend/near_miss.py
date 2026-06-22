import json
from pathlib import Path
from typing import Any


NEAR_MISS_PATH = Path(__file__).parent / "data" / "near_misses.json"


def _load_all() -> list[dict]:
    with open(NEAR_MISS_PATH) as f:
        return json.load(f)


def find_similar_incidents(zone: dict, score: int, reasons: list[dict]) -> list[dict]:
    all_records = _load_all()
    active_factors = set()

    for r in reasons:
        t = r["t"].lower()
        if "hot work" in t:
            active_factors.add("hot_work_permit")
        if "gas" in t and ("rising" in t or "threshold" in t):
            active_factors.add("rising_gas_trend")
        if "confined space" in t:
            active_factors.add("confined_space_entry")
        if "changeover" in t:
            active_factors.add("shift_changeover_window")
        if "welding" in t:
            active_factors.add("welding_permit")
        if "worker density" in t:
            active_factors.add("high_worker_density")
        if "maintenance" in t:
            active_factors.add("maintenance_activity")

    scored: list[tuple[int, dict]] = []
    for record in all_records:
        record_factors = set(record.get("contributing_factors", []))
        overlap = len(active_factors & record_factors)
        if overlap > 0 and record.get("zone") == zone.get("id"):
            overlap += 2
        if overlap > 0:
            scored.append((overlap, record))

    scored.sort(key=lambda x: -x[0])
    matches = [item[1] for item in scored[:3]]

    for m in matches:
        m["match_score"] = round((m.get("score_at_detection", 0) + score) / 2)

    return matches


def get_pattern_insights(zone: dict, reasons: list[dict]) -> str | None:
    matches = find_similar_incidents(zone, zone.get("score", 0), reasons)
    if not matches:
        return None

    top = matches[0]
    return (
        f"This pattern matches a documented near-miss ({top['id']}) "
        f"in {top['zone_name']} on {top['date']}. "
        f"{top['outcome']} Lesson: {top['lessons']}"
    )
