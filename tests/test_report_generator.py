import pytest
import sys
sys.path.insert(0, "backend")

from report_generator import generate_incident_report, generate_pdf


SAMPLE_ZONE = {
    "id": "Z3",
    "name": "Gas Processing",
    "score": 85,
    "riskLabel": "CRITICAL",
    "currentGas": 48,
    "gasThresh": 50,
    "permit": "hot_work",
    "maintenance": "confined_space_entry",
    "changeover": True,
    "workers": 6,
}


def test_generate_incident_report_returns_all_fields():
    reasons = [
        {"w": "+30", "t": "Gas reading approaching threshold", "pct": 96},
        {"w": "+40", "t": "Hot work permit active + rising gas trend", "pct": None},
        {"w": "+20", "t": "Confined space entry in progress", "pct": None},
        {"w": "+15", "t": "Shift changeover - reduced supervision continuity", "pct": None},
    ]
    report = generate_incident_report(SAMPLE_ZONE, reasons, 6)
    assert report["zone"]["id"] == "Z3"
    assert report["zone"]["name"] == "Gas Processing"
    assert report["trigger_score"] == 85
    assert report["risk_label"] == "CRITICAL"
    assert "contributing_factors" in report
    assert len(report["contributing_factors"]) == 4
    assert "evacuation_checklist" in report
    assert "regulatory_citations" in report
    assert "timestamp" in report or "generated_at" in report


def test_incident_report_has_evacuation_checklist():
    report = generate_incident_report(SAMPLE_ZONE, [{"w": "+30", "t": "Gas high", "pct": 90}], 4)
    assert len(report["evacuation_checklist"]) >= 4
    assert any("suspend" in item.lower() for item in report["evacuation_checklist"])


def test_generate_pdf_returns_bytes():
    report = generate_incident_report(SAMPLE_ZONE, [{"w": "+30", "t": "Gas high", "pct": 90}], 4)
    pdf = generate_pdf(report)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 0
    assert pdf.startswith(b"%PDF")


def test_generate_pdf_is_valid_and_contains_metadata():
    report = generate_incident_report(SAMPLE_ZONE, [{"w": "+30", "t": "Gas high", "pct": 90}], 4)
    pdf = generate_pdf(report)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert b"/Type /Catalog" in pdf
