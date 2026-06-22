from typing import Any


def compute_compound_risk(zone: dict, gas_history: list[int] | None = None) -> tuple[int, list[dict]]:
    score = 0
    reasons: list[dict] = []

    current_gas = zone.get("currentGas", zone.get("baseGas", 0))
    gas_thresh = zone.get("gasThresh", 50)
    pct = current_gas / gas_thresh if gas_thresh > 0 else 0

    if pct > 0.8:
        score += 30
        reasons.append({"w": "+30", "t": "Gas reading approaching threshold", "pct": round(pct * 100)})
    elif pct > 0.6:
        score += 15
        reasons.append({"w": "+15", "t": "Gas elevated (>60% of threshold)", "pct": round(pct * 100)})

    gas_trending = False
    if gas_history and len(gas_history) > 2:
        gas_trending = gas_history[-1] > gas_history[-3] + 3

    permit = zone.get("permit")
    if permit == "hot_work" and gas_trending:
        score += 40
        reasons.append({"w": "+40", "t": "Hot work permit active + rising gas trend", "pct": None})
    elif permit == "hot_work":
        score += 15
        reasons.append({"w": "+15", "t": "Hot work permit active in zone", "pct": None})
    elif permit == "welding":
        score += 8
        reasons.append({"w": "+8", "t": "Welding permit active", "pct": None})

    maintenance = zone.get("maintenance")
    if maintenance == "confined_space_entry":
        score += 20
        reasons.append({"w": "+20", "t": "Confined space entry in progress", "pct": None})

    if zone.get("changeover"):
        score += 15
        reasons.append({"w": "+15", "t": "Shift changeover — reduced supervision continuity", "pct": None})

    workers = zone.get("workers", 0)
    if workers > 4:
        score += 5
        reasons.append({"w": "+5", "t": "High worker density in zone", "pct": None})

    score = min(score, 100)
    return score, reasons


def get_risk_label(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 31:
        return "MEDIUM"
    return "LOW"
