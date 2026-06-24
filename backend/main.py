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

_BACKEND_DIR = str(Path(__file__).parent.resolve())
_PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())
for _p in (_BACKEND_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_ON_VERCEL = os.environ.get("VERCEL") is not None

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from risk_engine import compute_compound_risk, get_risk_label
from llm_reasoner import generate_risk_explanation
from alerts import dispatch_alert, get_alert_log, ALERT_LOG
from report_generator import generate_incident_report, generate_pdf
from near_miss import find_similar_incidents, get_pattern_insights
from database import (
    init_db, get_all_zones, get_zone, update_zone,
    add_gas_reading, get_gas_history,
    insert_alert, get_recent_alerts,
    insert_incident, get_all_incidents, reset_all, close_db,
)

app = FastAPI(title="SafetyIQ API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

manager = ConnectionManager()

# ---------------------------------------------------------------------------
# Simulation state (kept in-memory for performance; persisted to SQLite)
# ---------------------------------------------------------------------------

sim_time = datetime(2026, 6, 22, 10, 14, 0, tzinfo=timezone.utc)
scenario_active = False

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _enrich_zone(z: dict) -> dict:
    z = dict(z)
    z["currentGas"] = z.get("current_gas") or z.get("currentGas") or z.get("base_gas", 20)
    gh = get_gas_history(z["id"])
    score, reasons = compute_compound_risk(z, gh)
    z["currentGas"] = round(float(z["currentGas"]), 1)
    z["score"] = score
    z["reasons"] = reasons
    z["riskLabel"] = get_risk_label(score)
    z["gasHistory"] = gh
    z["gasThresh"] = z.get("gas_thresh", z.get("gasThresh", 50))
    z["baseGas"] = z.get("base_gas", z.get("baseGas", 20))
    z["changeover"] = bool(z.get("changeover", False))
    z["workers"] = z.get("workers", 0)
    return z


def _build_dashboard():
    zones = [_enrich_zone(z) for z in get_all_zones()]
    alert_count = sum(1 for z in zones if z["score"] >= 61)
    max_zone = max(zones, key=lambda x: x["score"]) if zones else {}
    return {
        "zones": zones,
        "metrics": {
            "zonesMonitored": len(zones),
            "workersOnFloor": sum(z.get("workers", 0) for z in zones),
            "activeAlerts": alert_count,
            "highestRiskZone": max_zone.get("id", ""),
            "highestRiskScore": max_zone.get("score", 0),
        },
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
    init_db()
    if not _ON_VERCEL:
        asyncio.create_task(_tick_broadcaster())


@app.on_event("shutdown")
async def shutdown():
    close_db()


async def _tick_broadcaster():
    """Broadcast dashboard state via WebSocket every 3 seconds."""
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
    return {"zones": [_enrich_zone(z) for z in get_all_zones()], "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/zones/{zone_id}")
def get_zone_endpoint(zone_id: str):
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
    global scenario_active
    scenario_active = True

    z = get_zone("Z3")
    if not z:
        raise HTTPException(404, "Zone Z3 not found")

    steps = [
        {"permit": "hot_work", "gas": 38, "msg": "Hot work permit activated"},
        {"gas": 41, "msg": "CO readings rising \u2014 41 ppm"},
        {"maintenance": "confined_space_entry", "workers": 8, "gas": 44, "msg": "Maintenance crew entered"},
        {"changeover": True, "gas": 46, "msg": "Shift changeover window open"},
        {"gas": 48, "msg": "Compound risk threshold breached"},
    ]

    results = []
    for step in steps:
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
        results.append({"score": enriched["score"], "label": get_risk_label(enriched["score"]), "message": step.get("msg", "")})

        if enriched["score"] >= 80:
            dispatch_results = await dispatch_alert("red", "COMPOUND RISK THRESHOLD BREACHED",
                "Z3 risk score crossed 80 \u2014 no single sensor flagged this", "Z3", enriched["score"])
            results.append({"action": "orchestrator_fired", "score": enriched["score"], "dispatch": dispatch_results})

    scenario_active = False
    return {"scenario": "vizag", "zone": "Z3", "steps": results}


@app.get("/api/zones/{zone_id}/explain")
def explain_zone(zone_id: str):
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    enriched = _enrich_zone(z)
    explanation = generate_risk_explanation(enriched, enriched["score"], enriched["reasons"])
    return explanation


@app.get("/api/zones/{zone_id}/near-misses")
def get_near_misses(zone_id: str):
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    enriched = _enrich_zone(z)
    matches = find_similar_incidents(enriched, enriched["score"], enriched["reasons"])
    insight = get_pattern_insights(enriched, enriched["reasons"])
    return {"matches": matches, "insight": insight}


@app.post("/api/incident/{zone_id}")
async def create_incident(zone_id: str):
    z = get_zone(zone_id)
    if not z:
        raise HTTPException(404, f"Zone {zone_id} not found")
    enriched = _enrich_zone(z)

    report = generate_incident_report(enriched, enriched["reasons"], enriched.get("workers", 0))
    insert_incident(report)

    dispatch_results = await dispatch_alert("red", f"Incident report generated for {zone_id}",
        f"Score: {enriched['score']}/100 \u2014 Emergency Response Orchestrator fired", zone_id, enriched["score"])

    return {"incident": report, "dispatched": dispatch_results}


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
    return _build_dashboard()


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
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
