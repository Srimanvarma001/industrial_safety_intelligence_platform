import json
from pathlib import Path
from typing import Any

print("[safetyiq:nm] near_miss.py loading")
NEAR_MISS_PATH = Path(__file__).parent / "data" / "near_misses.json"
print(f"[safetyiq:nm] NEAR_MISS_PATH = {NEAR_MISS_PATH}, exists = {NEAR_MISS_PATH.exists()}")


def _load_all() -> list[dict]:
    print(f"[safetyiq:nm] _load_all from {NEAR_MISS_PATH}")
    try:
        with open(NEAR_MISS_PATH) as f:
            data = json.load(f)
        print(f"[safetyiq:nm] loaded {len(data)} near-miss records")
        return data
    except Exception as e:
        print(f"[safetyiq:nm] FAILED to load near-misses: {e}")
        import traceback; traceback.print_exc()
        return []


def find_similar_incidents(zone: dict, score: int, reasons: list[dict]) -> list[dict]:
    print(f"[safetyiq:nm] >>> find_similar_incidents({zone.get('id', '?')}, score={score})")
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

    print(f"[safetyiq:nm] active_factors: {active_factors}")

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
        m["incident_id"] = m["id"]

    print(f"[safetyiq:nm] <<< found {len(matches)} matches")
    return matches


def get_pattern_insights(zone: dict, reasons: list[dict]) -> str | None:
    print(f"[safetyiq:nm] >>> get_pattern_insights({zone.get('id', '?')})")
    matches = find_similar_incidents(zone, zone.get("score", 0), reasons)
    if not matches:
        print("[safetyiq:nm] no matches, no insight")
        return None

    top = matches[0]
    insight = (
        f"This pattern matches a documented near-miss ({top['id']}) "
        f"in {top['zone_name']} on {top['date']}. "
        f"{top['outcome']} Lesson: {top['lessons']}"
    )
    print(f"[safetyiq:nm] insight generated: {insight[:80]}...")
    return insight

print("[safetyiq:nm] near_miss.py loaded OK")
