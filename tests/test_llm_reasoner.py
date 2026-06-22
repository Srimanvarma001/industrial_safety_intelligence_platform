import pytest
import sys
sys.path.insert(0, "backend")

from llm_reasoner import generate_risk_explanation, retrieve_relevant_regulations

SAMPLE_ZONE = {
    "id": "Z3",
    "name": "Gas Processing",
    "currentGas": 38,
    "gasThresh": 50,
    "permit": "hot_work",
    "maintenance": "confined_space_entry",
    "changeover": True,
    "workers": 6,
}


def test_generate_risk_explanation_returns_all_fields():
    score, reasons = 75, [
        {"w": "+30", "t": "Gas reading approaching threshold", "pct": 90},
        {"w": "+40", "t": "Hot work permit active + rising gas trend", "pct": None},
    ]
    result = generate_risk_explanation(SAMPLE_ZONE, score, reasons)
    assert result["zone_id"] == "Z3"
    assert result["zone_name"] == "Gas Processing"
    assert result["score"] == 75
    assert result["label"] in ("HIGH", "CRITICAL")
    assert "explanation" in result
    assert "regulatory_citations" in result


def test_explanation_includes_contributing_factors():
    score, reasons = 50, [
        {"w": "+15", "t": "Hot work permit active in zone", "pct": None},
    ]
    result = generate_risk_explanation(SAMPLE_ZONE, score, reasons)
    assert "Hot work permit" in result["explanation"]
    assert str(result["score"]) in result["explanation"]


def test_explanation_mentions_hot_work_gas_combination():
    score, reasons = 70, [
        {"w": "+40", "t": "Hot work permit active + rising gas trend", "pct": None},
        {"w": "+20", "t": "Confined space entry in progress", "pct": None},
    ]
    result = generate_risk_explanation(SAMPLE_ZONE, score, reasons)
    assert "ignition source" in result["explanation"].lower()
    assert "Vizag" in result["explanation"]


def test_explanation_mentions_confined_space():
    score, reasons = 60, [
        {"w": "+20", "t": "Confined space entry in progress", "pct": None},
    ]
    result = generate_risk_explanation(SAMPLE_ZONE, score, reasons)
    assert "confined space" in result["explanation"].lower()
    assert "egress" in result["explanation"].lower()


def test_explanation_mentions_changeover():
    score, reasons = 55, [
        {"w": "+15", "t": "Shift changeover — reduced supervision continuity", "pct": None},
    ]
    result = generate_risk_explanation(SAMPLE_ZONE, score, reasons)
    assert "changeover" in result["explanation"].lower()
    assert "handoff" in result["explanation"].lower()


def test_retrieve_regulations_returns_list():
    regs = retrieve_relevant_regulations(SAMPLE_ZONE)
    assert isinstance(regs, list)
    assert len(regs) <= 3
    for r in regs:
        assert "standard" in r
        assert "section" in r
        assert "text" in r
        assert "id" in r


def test_retrieve_regulations_without_permit():
    zone = dict(SAMPLE_ZONE, permit=None, maintenance=None, changeover=False, currentGas=0, workers=2)
    regs = retrieve_relevant_regulations(zone)
    assert isinstance(regs, list)


def test_explanation_handles_low_score():
    zone = dict(SAMPLE_ZONE, currentGas=5)
    score, reasons = 0, []
    result = generate_risk_explanation(zone, score, reasons)
    assert result["score"] == 0
    assert result["label"] == "LOW"
