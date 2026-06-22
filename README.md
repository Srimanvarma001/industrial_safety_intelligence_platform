# SafetyIQ — AI-Powered Industrial Safety Platform

An AI-driven real-time safety monitoring platform for heavy industrial facilities (steel plants, refineries, chemical processing). Built for the ET AI Hackathon 2026.

## Overview

SafetyIQ fuses data from gas sensors, permit-to-work logs, maintenance logs, shift schedules, and worker location pings to detect dangerous compound risk conditions **before any single sensor threshold is breached**.

- **Risk Engine** — 6 composable weighted rules produce a per-zone risk score (0–100)
- **Geospatial Heatmap** — 8-zone plant grid color-coded by risk level with drill-down details
- **LLM Reasoning** — Keyword RAG over OISD/Factory Act regulatory corpus for explainable risk descriptions
- **Alert Orchestration** — Multi-channel dispatch (in-app, SMS, webhook, Slack) via real HTTP calls
- **Incident Reports** — Auto-generated PDF reports with contributing factors, regulatory citations, and evacuation checklists

## Tech Stack

| Layer | |
|---|---|
| **Frontend** | Modular SPA — Vanilla JS ES modules + Chart.js (no framework dependency) |
| **Backend** | FastAPI (Python 3.13) — 17 REST endpoints + WebSocket |
| **Database** | SQLite (persistent, schema-driven) |
| **Real-time** | WebSocket push (auto-reconnect), REST polling fallback |
| **Risk Engine** | Python + JavaScript (dual redundancy) |
| **RAG** | Keyword-based retrieval over OISD/Factory Act excerpts |
| **Alert Dispatch** | Real HTTP calls via httpx (configurable webhooks; simulated fallback) |
| **PDF** | fpdf2 |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn backend.main:app --reload
```

Open `http://localhost:8000` in a browser — the frontend SPA is served automatically.

## Project Structure

```
├── backend/
│   ├── main.py               # FastAPI server (17 REST endpoints + WebSocket)
│   ├── database.py           # SQLite persistence layer
│   ├── risk_engine.py        # Compound risk detection
│   ├── llm_reasoner.py       # OISD RAG + explanation generator
│   ├── alerts.py             # Multi-channel alert dispatch (HTTP + simulated)
│   ├── report_generator.py   # PDF incident report generation
│   ├── near_miss.py          # Historical pattern matcher
│   └── data/                 # Regulatory excerpts & near-miss records
├── frontend/                 # Modular SPA (ES modules, no build step)
│   ├── index.html            # Shell
│   ├── css/styles.css        # Styles
│   └── js/
│       ├── app.js            # Main orchestrator
│       ├── api.js            # API layer + WebSocket client
│       ├── risk-engine.js    # Score computation (JS mirror of Python engine)
│       ├── constants.js      # Thresholds & defaults
│       └── components/       # UI components
│           ├── zone-grid.js
│           ├── zone-detail.js
│           ├── incident-modal.js
│           └── alert-feed.js
├── data_generator.py          # Synthetic event stream generator
├── tests/                     # Pytest test suite (35 tests)
└── requirements.txt
```

## Environment Variables (Alert Dispatch)

| Variable | Purpose |
|---|---|
| `SAFETYIQ_WEBHOOK_URL` | URL for Emergency Response Team webhook |
| `SAFETYIQ_SLACK_URL` | Slack webhook URL for `#safety-alerts` |
| `SAFETYIQ_SMS_URL` | SMS gateway API endpoint |
| `SAFETYIQ_SMS_API_KEY` | API key for SMS gateway |

When unset, alerts fall back to simulated delivery.
