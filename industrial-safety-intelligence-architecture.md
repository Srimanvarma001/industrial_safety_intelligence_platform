# AI-Powered Industrial Safety Intelligence Platform
### Compound Risk Detection + Geospatial Heatmap + Emergency Response Orchestrator
**ET AI Hackathon 2026 — Problem Statement 1: Industrial Intelligence / Worker Safety**

---

## 1. Problem Recap

Indian heavy industry doesn't lack safety data — it lacks an **intelligence layer** that connects sensor readings, permits, maintenance activity, and shift logs into a single real-time risk picture. The Visakhapatnam Steel Plant explosion (Jan 2025) is the canonical example: gas sensors had functioning data, but nothing fused that data with operational context (active permits, maintenance state) in time to act.

**Our thesis:** A fatality is rarely caused by one bad reading. It's caused by a *combination* of conditions that, individually, look normal — and nobody is watching for the combination.

---

## 2. Solution Overview

We build a three-layer platform:

1. **Compound Risk Detection Engine** — fuses multiple synthetic data streams (gas sensors, permits, maintenance logs, shift changeovers, worker location) and flags dangerous *combinations* that no single sensor would catch alone.
2. **Geospatial Safety Heatmap** — renders live risk-by-zone over a plant floor plan, so a safety officer can see the entire facility's risk posture at a glance, updating in real time as conditions change.
3. **Emergency Response Orchestrator** — on a confirmed high-risk trigger, automatically fires alerts across 4 channels, generates a preliminary incident report with regulatory citations, matches the pattern against historical near-misses, and produces a downloadable PDF — turning "the critical first 10 minutes" from chaos into a logged, coordinated response.

This directly maps to the problem statement's two highest-weighted judging criteria: **Innovation (25%)** — combinatorial detection rather than threshold alerts — and **Business Impact (25%)** — demonstrable reduction in time-to-detection and false negatives, the stated metric that "actually saves lives."

---

## 3. System Architecture

```
                         ┌─────────────────────────────────────────┐
                         │            DATA SOURCES (synthetic)       │
                         │                                           │
                         │  • Gas Sensor Stream (ppm, zone, time)    │
                         │  • Permit-to-Work Log (type, zone, status)│
                         │  • Maintenance Activity Log                │
                         │  • Shift Changeover Schedule                │
                         │  • Worker Location Pings (zone, id, time) │
                         └───────────────────┬───────────────────────┘
                                             │
                                             ▼
                         ┌─────────────────────────────────────────┐
                         │         INGESTION & NORMALIZATION         │
                         │   (data_generator.py → FastAPI backend,   │
                         │    JSON schema, in-memory state)          │
                         └───────────────────┬───────────────────────┘
                                             │
                                             ▼
                         ┌─────────────────────────────────────────┐
                         │     COMPOUND RISK DETECTION ENGINE        │
                         │                                           │
                         │  • Rule layer: 6 composable risk rules     │
                         │    (gas, permit, maintenance, shift,       │
                         │     worker density, trending)             │
                         │  • Weighted risk score per zone (0–100)    │
                         │  • LLM reasoning layer: keyword RAG over   │
                         │    OISD/Factory Act corpus, generates      │
                         │    structured explanation with citations   │
                         └───────────────┬─────────────────┬─────────┘
                                         │                 │
                           risk score per zone      confirmed high-risk trigger
                                         │                 │
                                         ▼                 ▼
                   ┌─────────────────────────┐   ┌─────────────────────────────┐
                   │  GEOSPATIAL HEATMAP      │   │  EMERGENCY RESPONSE          │
                   │  (plant layout overlay)  │   │  ORCHESTRATOR                │
                   │                          │   │                              │
                   │  • Color-coded zones     │   │  • 4-channel alert dispatch   │
                   │    (green/yellow/red)    │   │    (in-app, SMS, webhook,    │
                   │  • Live polling every 3s │   │     Slack)                   │
                   │  • Drill-down per zone:  │   │  • Auto-generated incident   │
                   │    gas trend sparkline,   │   │    report with cause chain   │
                   │    permits, maintenance,  │   │  • OISD/Factory Act reg      │
                   │    workers, risk factors  │   │    citations via RAG         │
                   │  • What-if gas slider     │   │  • Near-miss pattern match   │
                   │  • Historical near-miss   │   │  • Downloadable PDF report   │
                   │    pattern display        │   │  • Evacuation checklist      │
                   └─────────────────────────┘   └─────────────────────────────┘
                                         │                 │
                                         └────────┬────────┘
                                                   ▼
                                   ┌─────────────────────────────────────┐
                                   │   SAFETY OFFICER DASHBOARD           │
                                   │  (single-page HTML + FastAPI backend)│
                                   │   responsive: desktop → tablet → mobile│
                                   └─────────────────────────────────────┘
```

### Mermaid version

```mermaid
flowchart TD
    A[Gas Sensor Stream] --> E[Ingestion & Normalization]
    B[Permit-to-Work Log] --> E
    C[Maintenance Activity Log] --> E
    D[Shift Changeover Schedule] --> E
    W[Worker Location Pings] --> E
    E --> F[Compound Risk Detection Engine]
    F -->|risk score per zone| G[Geospatial Heatmap]
    F -->|confirmed high-risk trigger| H[Emergency Response Orchestrator]
    F --> I[LLM Reasoning Layer<br/>(OISD RAG)] --> G
    F --> I
    H --> J[Near-Miss Pattern Matcher] --> H
    G --> K[Safety Officer Dashboard]
    H --> K
    L[Synthetic Data Generator] --> E
```

---

## 4. Component Detail

### 4.1 Data Ingestion Layer

All data sources are **synthetic but schema-realistic**, driven by two mechanisms:

- **`data_generator.py`** — standalone Python script that streams JSON events (gas readings, permits, maintenance, worker locations) to stdout or directly to the FastAPI backend. Supports a scripted Vizag scenario injection.
- **Built-in JS simulation** — the frontend runs a lightweight tick loop that adds Gaussian noise to gas readings every 3 seconds, maintaining full offline demo capability.

Sample event schemas:

```json
// Gas sensor reading
{
  "event_type": "gas_reading",
  "zone_id": "Z3",
  "gas_type": "CO",
  "ppm": 42,
  "threshold_ppm": 50,
  "timestamp": "2026-06-22T10:15:32Z"
}

// Permit-to-work
{
  "event_type": "permit",
  "permit_id": "PTW-2291",
  "permit_type": "hot_work",
  "zone_id": "Z3",
  "status": "active",
  "issued_at": "2026-06-22T09:50:00Z",
  "expires_at": "2026-06-22T13:50:00Z"
}

// Maintenance activity
{
  "event_type": "maintenance",
  "zone_id": "Z3",
  "activity": "confined_space_entry",
  "status": "in_progress",
  "crew_size": 3,
  "timestamp": "2026-06-22T10:12:00Z"
}

// Shift changeover
{
  "event_type": "shift_changeover",
  "zone_id": "Z3",
  "window_start": "2026-06-22T10:30:00Z",
  "window_end": "2026-06-22T10:45:00Z"
}

// Worker location ping
{
  "event_type": "worker_location",
  "worker_id": "W-118",
  "zone_id": "Z3",
  "timestamp": "2026-06-22T10:16:00Z"
}
```

### 4.2 Compound Risk Detection Engine

**Rule layer** — encodes 6 composable risk rules with weighted scoring:

| Rule | Weight | Condition |
|---|---|---|
| Gas approaching threshold | +30 | `currentGas > 80% of gasThresh` |
| Gas elevated | +15 | `currentGas > 60% of gasThresh` |
| Hot work + rising gas trend | +40 | `permit=hot_work AND gasTrending=true` |
| Hot work permit active | +15 | `permit=hot_work` (no trend) |
| Welding permit active | +8 | `permit=welding` |
| Confined space entry | +20 | `maintenance=confined_space_entry` |
| Shift changeover window | +15 | `changeover=true` |
| High worker density | +5 | `workers > 4` |

Implemented in both **Python** (`backend/risk_engine.py`) and **JavaScript** (frontend fallback) for dual-engine redundancy.

```python
def compound_risk_score(zone_state, gas_history=None):
    score = 0
    reasons = []

    if zone_state.gas_ppm > 0.8 * zone_state.gas_threshold:
        score += 30
        reasons.append("Gas reading approaching threshold")

    if zone_state.active_permit_type == "hot_work" and zone_state.gas_ppm_rising:
        score += 40
        reasons.append("Hot work permit active during rising gas trend")

    if zone_state.maintenance_activity == "confined_space_entry":
        score += 20
        reasons.append("Confined space entry in progress")

    if zone_state.in_shift_changeover_window:
        score += 15
        reasons.append("Shift changeover window — reduced supervision continuity")

    if zone_state.worker_count > 4:
        score += 5
        reasons.append("High worker density in zone")

    return min(score, 100), reasons
```

**LLM Reasoning Layer (OISD RAG)** — keyword-based retrieval over a curated corpus of 10 OISD/Factory Act excerpts. When a zone is selected, the backend (`llm_reasoner.py`):

1. Extracts context keywords from the zone state (permit type, maintenance type, changeover status, gas level)
2. Scores regulatory excerpts by keyword overlap with zone context + zone name
3. Returns top-3 matches with full text citations
4. Generates a plain-language explanation of *why* the combination is dangerous, referencing the Vizag incident pattern

### 4.3 Geospatial Safety Heatmap

- **8-zone plant grid** rendered as a responsive CSS grid: 4 columns on desktop, 3 on tablet, 2 on mobile
- Each zone color-coded: **green** (0–30), **yellow** (31–60), **red** (61–100) with animated pulse for critical zones
- Click any zone → right panel drill-down shows:
  - Gas trend sparkline (Chart.js, last 12 readings)
  - Current reading vs threshold with utilisation %
  - Active permits, maintenance status, shift changeover window
  - Worker count
  - Stacked risk factors with individual weights
  - **AI Risk Analysis** — LLM-generated explanation with OISD/Factory Act regulatory citations
  - **Historical Pattern Match** — near-miss records with overlapping risk factor profiles
  - **What-If Slider** — interactive gas level adjustment with live score recalculation
- Responsive layout: sidebar collapses below main content on tablets/phones
- Sticky topbar with clock, connection status indicator, and scenario controls

### 4.4 Emergency Response Orchestrator

Triggered when a zone's combined risk score crosses the configurable HIGH threshold (≥ 61):

1. **4-channel alert dispatch** (`alerts.py`):
   - 📣 Safety Officer (in-app notification)
   - 📱 Shift Supervisor (SMS simulation)
   - 🔔 Emergency Response Team (webhook to `https://hooks.safetyiq.internal/ert`)
   - 💬 #safety-alerts (Slack webhook simulation)
   Each channel reports delivery status (delivered/failed) displayed in the incident modal.

2. **Evidence snapshot** — freezes contributing sensor readings, active permits, maintenance state, and worker locations at trigger time, displayed in the incident report.

3. **Auto-generated incident report** — structured summary including:
   - Incident ID and timestamp
   - Zone details and trigger score
   - Contributing factors with weights
   - Regulatory clause references (OISD + Factory Act)
   - Workers in zone at trigger
   - Evacuation checklist
   - Lead time estimate

4. **Multi-channel dispatch display** — the incident modal shows all 4 alert channels with individual delivery timestamps.

5. **PDF download** — `report_generator.py` uses fpdf2 to generate a formatted, downloadable PDF version of the incident report via `/api/incident/{zone}/pdf`.

6. **Historical pattern match** — `near_miss.py` compares the current incident's risk factor vector against 5 documented near-miss records, returning the top matches with outcome summaries and lessons learned. Displayed in the zone detail panel alongside the LLM analysis.

### 4.5 Project Structure

```
industrial-safety/
├── industrial_safety_intelligence_platform.html   # Single-page frontend (responsive)
├── industrial-safety-intelligence-architecture.md  # This document
├── data_generator.py                              # Synthetic event stream generator
└── backend/
    ├── main.py                                    # FastAPI server (16 endpoints)
    ├── risk_engine.py                             # Compound risk detection engine
    ├── llm_reasoner.py                            # OISD RAG + explanation generator
    ├── alerts.py                                  # Multi-channel alert dispatch
    ├── report_generator.py                        # PDF incident report generation
    ├── near_miss.py                               # Historical pattern matcher
    └── data/
        ├── oisd_excerpts.json                     # 10 OISD/Factory Act excerpts
        └── near_misses.json                       # 5 historical near-miss records
```

---

## 5. Tech Stack (Implemented)

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML/CSS/JS + Chart.js (CDN) — no framework dependency |
| Backend API | FastAPI (Python 3.13) — 16 REST endpoints |
| State management | In-memory (Python dicts) + localStorage-ready frontend fallback |
| Risk engine | Python (`backend/risk_engine.py`) + JavaScript dual implementation |
| RAG corpus | 10 curated OISD/Factory Act excerpts, keyword-based retrieval |
| PDF generation | fpdf2 |
| Alert dispatch | httpx (async webhook calls) |
| Data generation | Python script (`data_generator.py`) + built-in JS simulator |
| Responsive design | Pure CSS with 4 breakpoints (1440px → 360px) |
| Charts | Chart.js 4.4.1 (sparkline gas trends) |

---

## 6. API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard` | Full dashboard state with metrics |
| GET | `/api/zones` | All zones with scores and gas history |
| GET | `/api/zones/{id}` | Single zone detail |
| POST | `/api/zones/{id}/update` | Update zone parameters |
| POST | `/api/tick` | Advance simulation tick |
| POST | `/api/scenario/trigger` | Run Vizag scenario sequence |
| GET | `/api/zones/{id}/explain` | LLM risk explanation with OISD citations |
| GET | `/api/zones/{id}/near-misses` | Historical pattern matches |
| POST | `/api/incident/{id}` | Generate incident report |
| GET | `/api/incident/{id}/pdf` | Download PDF report |
| GET | `/api/alerts` | Alert dispatch log |
| GET | `/api/incidents` | Incident history |

---

## 7. Demo Script (~3–4 minutes)

1. **Open on the dashboard** — plant heatmap, all zones green/yellow. Connection status shows "● API" confirming backend is live. Briefly narrate the problem (Vizag incident, data-present-but-unacted-upon pattern).
2. **Click any zone** — right panel shows gas sparkline, permits, maintenance status, stacked risk factors, AI risk analysis with OISD citations, and historical near-miss matches.
3. **Try the What-If slider** — drag the gas level up and watch the score recalculate in real time. Show how the zone transitions from green → yellow → red as the compound score climbs.
4. **Trigger the scripted scenario** — hot work permit issued in Zone 3, gas readings begin trending up, maintenance crew enters confined space, shift changeover window opens.
5. **Watch the compound score climb** — zone turns yellow, then red, with the side panel showing the stacking reasons. Note: no single sensor threshold was breached.
6. **Orchestrator fires** — incident modal appears showing 4 alert channels (all "delivered"), contributing factors with weights, 8 affected workers, OISD regulatory citations, and a 6-step evacuation checklist.
7. **Download the PDF** — click the "Download PDF Report" button to show the formatted incident document.
8. **Close on impact framing** — lead time gained (~12 minutes), and tie back to judging criteria: compound detection accuracy, lead time, reduced false negatives.

---

## 8. Mapping to Judging Criteria

| Criteria | Weight | How this solution addresses it |
|---|---|---|
| Innovation | 25% | Compound/multi-signal detection vs. single-sensor thresholds — the core novel mechanism. What-if slider for interactive exploration. |
| Business Impact | 25% | Closes the full loop: detection → visualization → automated action → documented report. Demonstrates ~12 min lead time advantage. |
| Technical Excellence | 20% | Multi-source fusion, OISD RAG/LLM reasoning layer with regulatory grounding, live geospatial rendering, PDF generation, historical pattern matching, dual Python/JS engines. |
| Scalability | 15% | Rule engine and schema are zone/sensor-type agnostic — same architecture extends to any plant layout, sensor mix, or additional risk rules. |
| User Experience | 15% | Single-pane responsive dashboard, drill-down without leaving heatmap view, interactive what-if slider, works on mobile through ultrawide. |

---

## 9. Future Scope

### Near-term (next iteration)

- **Persistent storage** — replace in-memory state with SQLite/PostgreSQL so data survives restarts and historical queries become possible across sessions.
- **Real WebSocket streaming** — replace 3-second polling with Server-Sent Events or WebSocket for true sub-second live updates.
- **OISD RAG upgrade** — replace keyword retrieval with embeddings (sentence-transformers + FAISS) for semantic search over the full OISD 116 standard and Factory Act text.
- **Multi-zone incidents** — when two or more zones breach HIGH simultaneously, show a prioritised incident queue with severity-based routing.
- **Authenticated user roles** — Safety Officer, Shift Supervisor, Plant Manager — each with different dashboard views and action permissions.

### Medium-term

- **Live sensor integration** — replace synthetic data with real Modbus/OPC-UA sensor feeds via an IIoT gateway (e.g. EMQX + MQTT bridge to FastAPI).
- **Dynamic risk rules** — allow safety officers to configure custom risk rules via a UI (weight adjustments, new factor types) without redeploying code.
- **What-if multi-variable** — extend the slider to adjust permit status, worker count, and maintenance state simultaneously, showing the combined score as a contour plot.
- **Incident timeline** — render a Gantt-style chronological view of every event leading to an incident (gas readings, permit issuances, maintenance entries) for post-mortem analysis.
- **Automated regulatory filing** — generate a complete OISD-compliant incident filing document (Form XII / Annexure A) with all required signatures and timestamps.

### Long-term stretch goals

- **Predictive risk engine** — train a lightweight time-series model (LSTM or Transformer) on historical sensor + incident data to predict compound risk scores 15–30 minutes ahead, moving from *reactive* to *predictive* safety.
- **Digital twin integration** — overlay the heatmap on a 3D BIM/CAD model of the plant floor for spatial awareness. Use WebGL (Three.js) for browser-based rendering.
- **Cross-plant aggregation** — federate dashboards across multiple facilities into a single corporate safety operations center view, with roll-up risk metrics per plant.
- **Mobile native app** — wrap the responsive web UI in a PWA or lightweight React Native shell with push notification support for alert delivery.
- **Voice-activated incident response** — integration with plant PA/announcement systems: "SafetyIQ: Automated announcement — Zone Z3, initiate evacuation. All personnel proceed to muster point B-3."

---

## 10. One-Line Pitch

> "Every fatal incident in this challenge had working sensors. What was missing wasn't data — it was a brain that connected it. We built that brain."
