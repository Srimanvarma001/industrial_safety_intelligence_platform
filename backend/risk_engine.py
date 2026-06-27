from typing import Any

print("[safetyiq:re] risk_engine.py loading")


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


def compute_single_sensor_risk(zone: dict) -> tuple[int, list[dict]]:
    current_gas = zone.get("currentGas", zone.get("baseGas", 0))
    gas_thresh = zone.get("gasThresh", 50)
    pct = current_gas / gas_thresh if gas_thresh > 0 else 0

    score = 0
    reasons = []
    if pct >= 1.0:
        score = 100
        reasons.append({"w": "+100", "t": "Gas threshold breached — standalone alarm", "pct": round(pct * 100)})
    elif pct > 0.8:
        score = 60
        reasons.append({"w": "+60", "t": "Gas near threshold (warning level)", "pct": round(pct * 100)})
    return score, reasons


def compute_detection_gap(compound_score: int, single_score: int) -> dict:
    return {
        "compound_detected": compound_score >= 61,
        "single_detected": single_score >= 61,
        "compound_only_detection": compound_score >= 61 > single_score,
        "compound_score": compound_score,
        "single_score": single_score,
        "gap_size": compound_score - single_score if compound_score >= 61 > single_score else 0,
    }


def get_risk_label(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 31:
        return "MEDIUM"
    return "LOW"


DETECTION_STATS = {
    "total_events": 0,
    "compound_detections": 0,
    "single_sensor_detections": 0,
    "compound_only_detections": 0,
    "compound_false_negatives": 0,
    "single_false_negatives": 0,
}


def record_detection_event(compound_score: int, single_score: int):
    DETECTION_STATS["total_events"] += 1
    if compound_score >= 61:
        DETECTION_STATS["compound_detections"] += 1
    if single_score >= 61:
        DETECTION_STATS["single_sensor_detections"] += 1
    if compound_score >= 61 > single_score:
        DETECTION_STATS["compound_only_detections"] += 1
    if compound_score < 61:
        DETECTION_STATS["compound_false_negatives"] += 1
    if single_score < 61 and compound_score >= 61:
        DETECTION_STATS["single_false_negatives"] += 1


def get_detection_summary() -> dict:
    t = DETECTION_STATS["total_events"]
    return {
        "total_events": t,
        "compound_detections": DETECTION_STATS["compound_detections"],
        "single_sensor_detections": DETECTION_STATS["single_sensor_detections"],
        "compound_only_detections": DETECTION_STATS["compound_only_detections"],
        "false_negative_rate_compound": round(DETECTION_STATS["compound_false_negatives"] / t * 100, 1) if t else 0,
        "false_negative_rate_single": round(DETECTION_STATS["single_false_negatives"] / t * 100, 1) if t else 0,
        "fnr_reduction": round(
            (DETECTION_STATS["single_false_negatives"] - DETECTION_STATS["compound_false_negatives"])
            / max(DETECTION_STATS["single_false_negatives"], 1) * 100, 1
        ) if DETECTION_STATS["single_false_negatives"] > 0 else 0,
    }


def reset_detection_stats():
    for k in DETECTION_STATS:
        DETECTION_STATS[k] = 0


print("[safetyiq:re] risk_engine.py loaded OK")
