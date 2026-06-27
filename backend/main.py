"""
SafetyIQ — Industrial Safety Intelligence Platform Backend
FastAPI server with WebSocket real-time streaming, SQLite persistence,
compound risk detection, LLM reasoning with OISD RAG, alert orchestration,
incident report generation, and historical near-miss matching.
"""

import asyncio
import json
import math
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

print("[safetyiq] === main.py starting ===")
print(f"[safetyiq] __file__ = {__file__}")
print(f"[safetyiq] __name__ = {__name__}")
print(f"[safetyiq] cwd = {os.getcwd()}")
print(f"[safetyiq] sys.path = {sys.path}")
print(f"[safetyiq] VERCEL env = {os.environ.get('VERCEL', 'not set')}")

_BACKEND_DIR = str(Path(__file__).parent.resolve())
_PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())
print(f"[safetyiq] BACKEND_DIR = {_BACKEND_DIR}")
print(f"[safetyiq] PROJECT_ROOT = {_PROJECT_ROOT}")
for _p in (_BACKEND_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
print(f"[safetyiq] sys.path after insert = {sys.path}")

_ON_VERCEL = os.environ.get("VERCEL") is not None
print(f"[safetyiq] _ON_VERCEL = {_ON_VERCEL}")

print("[safetyiq] importing fastapi...")
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
print("[safetyiq] fastapi imported OK")

print("[safetyiq] importing risk_engine...")
from risk_engine import (
    compute_compound_risk, compute_single_sensor_risk, compute_detection_gap,
    get_risk_label, get_detection_summary, record_detection_event, reset_detection_stats,
)
print("[safetyiq] risk_engine imported OK")

print("[safetyiq] importing llm_reasoner...")
from llm_reasoner import generate_risk_explanation
print("[safetyiq] llm_reasoner imported OK")

print("[safetyiq] importing alerts...")
from alerts import dispatch_alert, get_alert_log, ALERT_LOG
print("[safetyiq] alerts imported OK")

print("[safetyiq] importing report_generator...")
from report_generator import generate_incident_report, generate_pdf
print("[safetyiq] report_generator imported OK")

print("[safetyiq] importing near_miss...")
from near_miss import find_similar_incidents, get_pattern_insights
print("[safetyiq] near_miss imported OK")

print("[safetyiq] importing database...")
from database import (
    init_db, get_all_zones, get_zone, update_zone,
    add_gas_reading, get_gas_history,
    insert_alert, get_recent_alerts,
    insert_incident, get_all_incidents, reset_all, close_db,
)
print("[safetyiq] database imported OK")

print("[safetyiq] creating FastAPI app...")
app = FastAPI(title="SafetyIQ API", version="2.0.0")
print("[safetyiq] FastAPI app created")

print("[safetyiq] adding CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print("[safetyiq] CORS middleware added")

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)

print("[safetyiq] creating ConnectionManager...")
manager = ConnectionManager()
print("[safetyiq] ConnectionManager created")

# ---------------------------------------------------------------------------
# Simulation state (kept in-memory for performance; persisted to SQLite)
# ---------------------------------------------------------------------------

sim_time = datetime(2026, 6, 22, 10, 14, 0, tzinfo=timezone.utc)
scenario_active = False
SCENARIO_STEP_INTERVAL_MINUTES = 3

_first_cross_times: dict[str, datetime] = {}
_incident_lead_times: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _enrich_zone(z: dict) -> dict:
    print(f"[safetyiq] _enrich_zone({z.get('id', '?')})")
    z = dict(z)
    z["currentGas"] = z.get("current_gas") or z.get("currentGas") or z.get("base_gas", 20)
    gh = get_gas_history(z["id"])
    score, reasons = compute_compound_risk(z, gh)
    single_score, single_reasons = compute_single_sensor_risk(z)
    z["currentGas"] = round(float(z["currentGas"]), 1)
    z["score"] = score
    z["reasons"] = reasons
    z["singleScore"] = single_score
    z["singleReasons"] = single_reasons
    z["detectionGap"] = compute_detection_gap(score, single_score)
    z["riskLabel"] = get_risk_label(score)
    z["gasHistory"] = gh
    z["gasThresh"] = z.get("gas_thresh", z.get("gasThresh", 50))
    z["baseGas"] = z.get("base_gas", z.get("baseGas", 20))
    z["changeover"] = bool(z.get("changeover", False))
    z["workers"] = z.get("workers", 0)

    record_detection_event(score, single_score)

    zid = z["id"]
    if score >= 61 and zid not in _first_cross_times:
        _first_cross_times[zid] = sim_time

    return z


def _build_dashboard():
    zones = [_enrich_zone(z) for z in get_all_zones()]
    alert_count = sum(1 for z in zones if z["score"] >= 61)
    max_zone = max(zones, key=lambda x: x["score"]) if zones else {}
    compound_only_count = sum(1 for z in zones if z.get("detectionGap", {}).get("compound_only_detection"))
    return {
        "zones": zones,
        "metrics": {
            "zonesMonitored": len(zones),
            "workersOnFloor": sum(z.get("workers", 0) for z in zones),
            "activeAlerts": alert_count,
            "highestRiskZone": max_zone.get("id", ""),
            "highestRiskScore": max_zone.get("score", 0),
        },
        "baselineComparison": {
            "compoundOnlyDetections": compound_only_count,
            "totalZones": len(zones),
            "compoundOnlyPct": round(compound_only_count / len(zones) * 100, 1) if zones else 0,
        },
        "detectionSummary": get_detection_summary(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

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
# Startup / Shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    print("[safetyiq] >>> startup event fired")
    try:
        init_db()
        print("[safetyiq] init_db() completed")
    except Exception as e:
        print(f"[safetyiq] init_db() FAILED: {e}")
        import traceback
        traceback.print_exc()
    if not _ON_VERCEL:
        asyncio.create_task(_tick_broadcaster())
        print("[safetyiq] background task created")
    print("[safetyiq] <<< startup done")


@app.on_event("shutdown")
async def shutdown():
    print("[safetyiq] >>> shutdown event")
    close_db()
    print("[safetyiq] <<< shutdown done")


async def _tick_broadcaster():
    while True:
        await asyncio.sleep(3)
        try:
            dashboard = _build_dashboard()
            await manager.broadcast(dashboard)
        except Exception as e:
            print(f"[ws broadcast] {e}")


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/zones")
def get_zones():
    print(f"[safetyiq] GET /api/zones")
    try:
        result = {"zones": [_enrich_zone(z) for z in get_all_zones()], "timestamp": datetime.now(timezone.utc).isoformat()}
        print(f"[safetyiq] GET /api/zones OK - {len(result['zones'])} zones")
        return result
    except Exception as e:
        print(f"[safetyiq] GET /api/zones FAILED: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))


@app.get("/api/zones/{zone_id}")
def get_zone_endpoint(zone_id: str):
    print(f"[safetyiq] GET /api/zones/{zone_id}")
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    return _enrich_zone(z)


@app.post("/api/zones/{zone_id}/update")
def update_zone_endpoint(zone_id: str, update: ZoneUpdate):
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")

    kwargs = {}
    if update.gas is not None:
        kwargs["current_gas"] = update.gas
        add_gas_reading(zone_id, round(update.gas))
    if update.permit is not None:
        kwargs["permit"] = update.permit if update.permit != "none" else None
    if update.maintenance is not None:
        kwargs["maintenance"] = update.maintenance if update.maintenance != "none" else None
    if update.changeover is not None:
        kwargs["changeover"] = int(update.changeover)
    if update.workers is not None:
        kwargs["workers"] = update.workers

    update_zone(zone_id, **kwargs)
    updated = get_zone(zone_id)
    enriched = _enrich_zone(updated)
    return {"zone_id": zone_id, "score": enriched["score"], "reasons": enriched["reasons"], "riskLabel": enriched["riskLabel"]}


@app.post("/api/scenario/trigger")
async def trigger_scenario():
    global sim_time, scenario_active
    scenario_active = True

    z = get_zone("Z3")
    if not z:
        raise HTTPException(404, "Zone Z3 not found")

    _first_cross_times.pop("Z3", None)
    lead_time_minutes = None
    first_cross_step = None

    steps = [
        {"permit": "hot_work", "gas": 38, "msg": "Hot work permit activated"},
        {"gas": 41, "msg": "CO readings rising \u2014 41 ppm"},
        {"maintenance": "confined_space_entry", "workers": 8, "gas": 44, "msg": "Maintenance crew entered"},
        {"changeover": True, "gas": 46, "msg": "Shift changeover window open"},
        {"gas": 48, "msg": "Compound risk threshold breached"},
    ]

    results = []
    for i, step in enumerate(steps):
        kwargs = {}
        if "permit" in step:
            kwargs["permit"] = step["permit"]
        if "gas" in step:
            kwargs["current_gas"] = step["gas"]
            add_gas_reading("Z3", step["gas"])
        if "maintenance" in step:
            kwargs["maintenance"] = step["maintenance"]
        if "workers" in step:
            kwargs["workers"] = step["workers"]
        if "changeover" in step:
            kwargs["changeover"] = int(step["changeover"])

        update_zone("Z3", **kwargs)
        enriched = _enrich_zone(get_zone("Z3"))

        if enriched["score"] >= 61 and first_cross_step is None:
            first_cross_step = i
            _first_cross_times["Z3"] = sim_time
            lead_time_minutes = (len(steps) - i) * SCENARIO_STEP_INTERVAL_MINUTES

        results.append({"score": enriched["score"], "label": get_risk_label(enriched["score"]), "message": step.get("msg", "")})

        if enriched["score"] >= 80:
            dispatch_results = await dispatch_alert("red", "COMPOUND RISK THRESHOLD BREACHED",
                "Z3 risk score crossed 80 \u2014 no single sensor flagged this", "Z3", enriched["score"])
            results.append({"action": "orchestrator_fired", "score": enriched["score"], "dispatch": dispatch_results})

        sim_time = sim_time.replace(minute=sim_time.minute + SCENARIO_STEP_INTERVAL_MINUTES)

    scenario_active = False
    return {
        "scenario": "vizag", "zone": "Z3", "steps": results,
        "leadTimeMinutes": lead_time_minutes,
        "firstCrossStep": first_cross_step,
    }


@app.get("/api/zones/{zone_id}/explain")
def explain_zone(zone_id: str):
    print(f"[safetyiq] >>> GET /api/zones/{zone_id}/explain")
    z = get_zone(zone_id)
    if not z:
        print(f"[safetyiq] zone {zone_id} not found for explain")
        raise HTTPException(404, f"Zone {zone_id} not found")
    enriched = _enrich_zone(z)
    try:
        explanation = generate_risk_explanation(enriched, enriched["score"], enriched["reasons"])
        print(f"[safetyiq] <<< explain OK for {zone_id}")
        return explanation
    except Exception as e:
        print(f"[safetyiq] explain FAILED for {zone_id}: {e}")
        import traceback; traceback.print_exc()
        raise


@app.get("/api/zones/{zone_id}/near-misses")
def get_near_misses(zone_id: str):
    print(f"[safetyiq] >>> GET /api/zones/{zone_id}/near-misses")
    z = get_zone(zone_id)
    if not z:
        print(f"[safetyiq] zone {zone_id} not found for near-misses")
        raise HTTPException(404, f"Zone {zone_id} not found")
    enriched = _enrich_zone(z)
    try:
        matches = find_similar_incidents(enriched, enriched["score"], enriched["reasons"])
        insight = get_pattern_insights(enriched, enriched["reasons"])
        print(f"[safetyiq] <<< near-misses OK for {zone_id}: {len(matches)} matches, insight={bool(insight)}")
        return {"matches": matches, "insight": insight}
    except Exception as e:
        print(f"[safetyiq] near-misses FAILED for {zone_id}: {e}")
        import traceback; traceback.print_exc()
        raise


@app.post("/api/incident/{zone_id}")
async def create_incident(zone_id: str):
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    enriched = _enrich_zone(z)

    lead_time_minutes = None
    first_cross = _first_cross_times.get(zone_id)
    if first_cross:
        delta = sim_time - first_cross
        lead_time_minutes = round(delta.total_seconds() / 60, 1)
        if lead_time_minutes < 0:
            lead_time_minutes = 0
        _incident_lead_times[zone_id] = lead_time_minutes

    report = generate_incident_report(enriched, enriched["reasons"], enriched.get("workers", 0))
    report["lead_time_minutes"] = lead_time_minutes
    insert_incident(report)

    dispatch_results = await dispatch_alert("red", f"Incident report generated for {zone_id}",
        f"Score: {enriched['score']}/100 \u2014 Emergency Response Orchestrator fired", zone_id, enriched["score"])

    return {
        "incident": report,
        "dispatched": dispatch_results,
        "leadTimeMinutes": lead_time_minutes,
        "detectionGap": enriched.get("detectionGap"),
    }


@app.get("/api/incident/{zone_id}/pdf")
def download_incident_pdf(zone_id: str):
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    enriched = _enrich_zone(z)
    report = generate_incident_report(enriched, enriched["reasons"], enriched.get("workers", 0))
    pdf_bytes = generate_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="incident_{zone_id}.pdf"'},
    )


@app.get("/api/alerts")
def list_alerts(limit: int = 20):
    return {"alerts": get_alert_log(limit)}


@app.get("/api/incidents")
def list_incidents():
    return {"incidents": get_all_incidents()}


@app.get("/api/dashboard")
def get_dashboard():
    print(f"[safetyiq] GET /api/dashboard")
    try:
        result = _build_dashboard()
        print(f"[safetyiq] GET /api/dashboard OK - {len(result.get('zones', []))} zones")
        return result
    except Exception as e:
        print(f"[safetyiq] GET /api/dashboard FAILED: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/tick")
def tick():
    global sim_time
    sim_time = sim_time.replace(second=(sim_time.second + 15) % 60)

    for z in get_all_zones():
        noise = (random.random() - 0.5) * 4
        current = (z.get("current_gas") or z.get("base_gas", 20)) + noise
        current = max(0, round(current, 1))
        update_zone(z["id"], current_gas=current)
        add_gas_reading(z["id"], round(current))

    return {"status": "ok", "simTime": sim_time.isoformat()}


@app.post("/api/reset")
async def reset():
    global sim_time
    sim_time = datetime(2026, 6, 22, 10, 14, 0, tzinfo=timezone.utc)
    ALERT_LOG.clear()
    _first_cross_times.clear()
    _incident_lead_times.clear()
    reset_detection_stats()
    reset_all()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if _ON_VERCEL:
        await ws.close(code=1000, reason="WebSocket not supported on Vercel")
        return
    await manager.connect(ws)
    try:
        dashboard = _build_dashboard()
        await ws.send_json({"type": "init", "data": dashboard})

        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await ws.send_json({"type": "pong"})
                elif msg.get("action") == "tick":
                    tick()
                    await ws.send_json({"type": "dashboard", "data": _build_dashboard()})
            except asyncio.TimeoutError:
                try:
                    await ws.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws] error: {e}")
    finally:
        await manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Serve frontend static files
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
print(f"[safetyiq] FRONTEND_DIR = {FRONTEND_DIR}, exists = {FRONTEND_DIR.is_dir()}")
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    print("[safetyiq] frontend mounted at /")

print("[safetyiq] === main.py module loaded OK ===")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
