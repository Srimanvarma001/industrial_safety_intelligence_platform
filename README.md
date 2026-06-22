# SafetyIQ — AI-Powered Industrial Safety Platform

An AI-driven real-time safety monitoring platform for heavy industrial facilities (steel plants, refineries, chemical processing). Built for the ET AI Hackathon 2026.

## Overview

SafetyIQ fuses data from gas sensors, permit-to-work logs, maintenance logs, shift schedules, and worker location pings to detect dangerous compound risk conditions **before any single sensor threshold is breached**.

- **Risk Engine** — 6 composable weighted rules produce a per-zone risk score (0–100)
- **Geospatial Heatmap** — 8-zone plant grid color-coded by risk level with drill-down details
- **LLM Reasoning** — Keyword RAG over OISD/Factory Act regulatory corpus for explainable risk descriptions
- **Alert Orchestration** — Multi-channel dispatch (in-app, SMS, webhook, Slack) when risk crosses threshold
- **Incident Reports** — Auto-generated PDF reports with contributing factors, regulatory citations, and evacuation checklists

## Tech Stack

| Layer | |
|---|---|
| **Frontend** | Vanilla HTML/CSS/JS + Chart.js |
| **Backend** | FastAPI (Python 3.13) |
| **Risk Engine** | Python + JavaScript (dual redundancy) |
| **RAG** | Keyword-based retrieval over OISD/Factory Act excerpts |
| **PDF** | fpdf2 |

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn httpx fpdf2 pydantic

# Start the server
uvicorn backend.main:app --reload
```

Open `industrial_safety_intelligence_platform.html` in a browser (serve via Live Server or open directly).

## Project Structure

```
├── backend/
│   ├── main.py               # FastAPI server (12 REST endpoints)
│   ├── risk_engine.py        # Compound risk detection
│   ├── llm_reasoner.py       # OISD RAG + explanation generator
│   ├── alerts.py             # Multi-channel alert dispatch
│   ├── report_generator.py   # PDF incident report generation
│   ├── near_miss.py          # Historical pattern matcher
│   └── data/                 # Regulatory excerpts & near-miss records
├── data_generator.py          # Synthetic event stream generator
└── industrial_safety_intelligence_platform.html  # Single-page frontend
```
