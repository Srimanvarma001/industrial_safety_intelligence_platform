"""
SafetyIQ — Industrial Safety Intelligence Platform Backend
FastAPI server implementing: compound risk detection engine,
LLM reasoning layer with OISD RAG, alert orchestration,
incident report generation, and historical near-miss matching.
"""

import asyncio
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from risk_engine import compute_compound_risk, get_risk_label
from llm_reasoner import generate_risk_explanation
from alerts import dispatch_alert, get_alert_log, ALERT_LOG
from report_generator import generate_incident_report, generate_pdf
from near_miss import find_similar_incidents, get_pattern_insights

app = FastAPI(title="SafetyIQ API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

ZONES = [
    {"id": "Z1", "name": "Blast Furnace A", "workers": 4, "baseGas": 28, "gasThresh": 50, "permit": None, "maintenance": None, "changeover": False},
    {"id": "Z2", "name": "Coke Oven Bay", "workers": 2, "baseGas": 18, "gasThresh": 45, "permit": "welding", "maintenance": None, "changeover": False},
    {"id": "Z3", "name": "Gas Processing", "workers": 5, "baseGas": 35, "gasThresh": 50, "permit": None, "maintenance": None, "changeover": False},
    {"id": "Z4", "name": "Ore Handling", "workers": 3, "baseGas": 12, "gasThresh": 60, "permit": "hot_work", "maintenance": None, "changeover": False},
    {"id": "Z5", "name": "Slag Yard", "workers": 2, "baseGas": 8, "gasThresh": 60, "permit": None, "maintenance": None, "changeover": False},
    {"id": "Z6", "name": "Steam Plant", "workers": 4, "baseGas": 22, "gasThresh": 50, "permit": None, "maintenance": None, "changeover": True},
    {"id": "Z7", "name": "Cooling Tower", "workers": 2, "baseGas": 5, "gasThresh": 45, "permit": None, "maintenance": None, "changeover": False},
    {"id": "Z8", "name": "Control Room", "workers": 2, "baseGas": 2, "gasThresh": 30, "permit": None, "maintenance": None, "changeover": False},
]

state = [dict(z) for z in ZONES]
gas_history: dict[str, list[int]] = {z["id"]: [z["baseGas"]] for z in state}
incident_log: list[dict] = []
sim_time = datetime(2026, 6, 22, 10, 14, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# JSON persistence
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
STATE_PATH = DATA_DIR / "persisted_state.json"


def _save_state():
    try:
        data = {
            "state": state,
            "gas_history": gas_history,
            "incident_log": incident_log,
            "alert_log": ALERT_LOG,
            "sim_time": sim_time.isoformat(),
        }
        with open(STATE_PATH, "w") as f:
            json.dump(data, f, default=str, indent=2)
    except Exception as e:
        print(f"[persist] Failed to save state: {e}")


def _load_state():
    global state, gas_history, incident_log, sim_time
    if not STATE_PATH.exists():
        return
    try:
        with open(STATE_PATH) as f:
            data = json.load(f)
        if "state" in data and len(data["state"]) == 8:
            state.clear()
            state.extend(data["state"])
            gas_history.clear()
            gas_history.update(data.get("gas_history", {}))
            incident_log.clear()
            incident_log.extend(data.get("incident_log", []))
            if "alert_log" in data:
                ALERT_LOG.clear()
                ALERT_LOG.extend(data["alert_log"])
            if "sim_time" in data:
                sim_time = datetime.fromisoformat(data["sim_time"])
    except Exception as e:
        print(f"[persist] Failed to load state: {e}")


_load_state()


def _get_zone(zid: str) -> dict:
    for z in state:
        if z["id"] == zid:
            return z
    raise HTTPException(404, f"Zone {zid} not found")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ZoneUpdate(BaseModel):
    gas: float | None = None
    permit: str | None = None
    maintenance: str | None = None
    changeover: bool | None = None
    workers: int | None = None

class ScenarioStep(BaseModel):
    zone_id: str
    actions: list[dict]

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/zones")
def get_zones():
    results = []
    for z in state:
        z_copy = dict(z)
        z_copy["currentGas"] = z_copy.get("currentGas", z_copy["baseGas"])
        score, reasons = compute_compound_risk(z_copy, gas_history.get(z_copy["id"]))
        z_copy["score"] = score
        z_copy["reasons"] = reasons
        z_copy["riskLabel"] = get_risk_label(score)
        z_copy["gasHistory"] = gas_history.get(z_copy["id"], [])
        results.append(z_copy)
    return {"zones": results, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/zones/{zone_id}")
def get_zone(zone_id: str):
    z = _get_zone(zone_id)
    z_copy = dict(z)
    z_copy["currentGas"] = z_copy.get("currentGas", z_copy["baseGas"])
    score, reasons = compute_compound_risk(z_copy, gas_history.get(zone_id))
    z_copy["score"] = score
    z_copy["reasons"] = reasons
    z_copy["riskLabel"] = get_risk_label(score)
    z_copy["gasHistory"] = gas_history.get(zone_id, [])
    return z_copy


@app.post("/api/zones/{zone_id}/update")
async def update_zone(zone_id: str, update: ZoneUpdate):
    z = _get_zone(zone_id)
    if update.gas is not None:
        z["currentGas"] = update.gas
        gh = gas_history.setdefault(zone_id, [])
        gh.append(round(update.gas))
        if len(gh) > 12:
            gh.pop(0)
    if update.permit is not None:
        z["permit"] = update.permit if update.permit != "none" else None
    if update.maintenance is not None:
        z["maintenance"] = update.maintenance if update.maintenance != "none" else None
    if update.changeover is not None:
        z["changeover"] = update.changeover
    if update.workers is not None:
        z["workers"] = update.workers

    score, reasons = compute_compound_risk(z, gas_history.get(zone_id))
    _save_state()
    return {"zone_id": zone_id, "score": score, "reasons": reasons, "riskLabel": get_risk_label(score)}


@app.post("/api/scenario/trigger")
async def trigger_scenario():
    z3 = _get_zone("Z3")
    steps = [
        {"permit": "hot_work", "gas": 38, "msg": "Hot work permit activated"},
        {"gas": 41, "msg": "CO readings rising — 41 ppm"},
        {"maintenance": "confined_space_entry", "workers": 8, "gas": 44, "msg": "Maintenance crew entered"},
        {"changeover": True, "gas": 46, "msg": "Shift changeover window open"},
        {"gas": 48, "msg": "Compound risk threshold breached"}
    ]

    results = []
    for step in steps:
        if "permit" in step:
            z3["permit"] = step["permit"]
        if "gas" in step:
            z3["currentGas"] = step["gas"]
            gh = gas_history.setdefault("Z3", [])
            gh.append(step["gas"])
            if len(gh) > 12:
                gh.pop(0)
        if "maintenance" in step:
            z3["maintenance"] = step["maintenance"]
        if "workers" in step:
            z3["workers"] = step["workers"]
        if "changeover" in step:
            z3["changeover"] = step["changeover"]

        score, reasons = compute_compound_risk(z3, gas_history.get("Z3"))
        results.append({"score": score, "label": get_risk_label(score), "message": step.get("msg", "")})

        if score >= 80:
            await dispatch_alert("red", "COMPOUND RISK THRESHOLD BREACHED",
                                "Z3 risk score crossed 80 — no single sensor flagged this", "Z3", score)
            results.append({"action": "orchestrator_fired", "score": score})

    _save_state()
    return {"scenario": "vizag", "zone": "Z3", "steps": results}


@app.get("/api/zones/{zone_id}/explain")
def explain_zone(zone_id: str):
    z = _get_zone(zone_id)
    z_copy = dict(z)
    z_copy["currentGas"] = z_copy.get("currentGas", z_copy["baseGas"])
    score, reasons = compute_compound_risk(z_copy, gas_history.get(zone_id))
    explanation = generate_risk_explanation(z_copy, score, reasons)
    return explanation


@app.get("/api/zones/{zone_id}/near-misses")
def get_near_misses(zone_id: str):
    z = _get_zone(zone_id)
    z_copy = dict(z)
    z_copy["currentGas"] = z_copy.get("currentGas", z_copy["baseGas"])
    score, reasons = compute_compound_risk(z_copy, gas_history.get(zone_id))
    matches = find_similar_incidents(z_copy, score, reasons)
    insight = get_pattern_insights(z_copy, reasons)
    return {"matches": matches, "insight": insight}


@app.post("/api/incident/{zone_id}")
async def create_incident(zone_id: str):
    z = _get_zone(zone_id)
    z_copy = dict(z)
    z_copy["currentGas"] = z_copy.get("currentGas", z_copy["baseGas"])
    score, reasons = compute_compound_risk(z_copy, gas_history.get(zone_id))
    z_copy["score"] = score

    report = generate_incident_report(z_copy, reasons, z_copy.get("workers", 0))
    incident_log.insert(0, report)

    dispatch_results = await dispatch_alert("red", f"Incident report generated for {zone_id}",
                                            f"Score: {score}/100 — Emergency Response Orchestrator fired", zone_id, score)
    _save_state()

    return {"incident": report, "dispatched": dispatch_results}


@app.get("/api/incident/{zone_id}/pdf")
def download_incident_pdf(zone_id: str):
    z = _get_zone(zone_id)
    z_copy = dict(z)
    z_copy["currentGas"] = z_copy.get("currentGas", z_copy["baseGas"])
    score, reasons = compute_compound_risk(z_copy, gas_history.get(zone_id))
    z_copy["score"] = score
    report = generate_incident_report(z_copy, reasons, z_copy.get("workers", 0))
    pdf_bytes = generate_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="incident_{zone_id}.pdf"'}
    )


@app.get("/api/alerts")
def list_alerts(limit: int = 20):
    return {"alerts": get_alert_log(limit)}


@app.get("/api/incidents")
def list_incidents():
    return {"incidents": incident_log}


@app.get("/api/dashboard")
def get_dashboard():
    results = []
    alert_count = 0
    for z in state:
        z_copy = dict(z)
        z_copy["currentGas"] = z_copy.get("currentGas", z_copy["baseGas"])
        score, reasons = compute_compound_risk(z_copy, gas_history.get(z["id"]))
        z_copy["score"] = score
        z_copy["reasons"] = reasons
        z_copy["riskLabel"] = get_risk_label(score)
        z_copy["gasHistory"] = gas_history.get(z["id"], [])
        if score >= 61:
            alert_count += 1
        results.append(z_copy)

    max_zone = max(results, key=lambda x: x["score"])
    return {
        "zones": results,
        "metrics": {
            "zonesMonitored": len(results),
            "workersOnFloor": sum(z.get("workers", 0) for z in state),
            "activeAlerts": alert_count,
            "highestRiskZone": max_zone["id"],
            "highestRiskScore": max_zone["score"]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/tick")
async def tick():
    global sim_time
    sim_time = sim_time.replace(second=(sim_time.second + 15) % 60)

    for z in state:
        noise = await asyncio.to_thread(lambda: (random.random() - 0.5) * 4)
        current = z.get("currentGas", z["baseGas"]) + noise
        current = max(0, current)
        z["currentGas"] = round(current, 1)

        gh = gas_history.setdefault(z["id"], [])
        gh.append(round(current))
        if len(gh) > 12:
            gh.pop(0)

    _save_state()
    return {"status": "ok", "simTime": sim_time.isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
