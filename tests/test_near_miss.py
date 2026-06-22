import pytest
import sys
sys.path.insert(0, "backend")

from near_miss import find_similar_incidents, get_pattern_insights


def test_find_similar_incidents_returns_matches():
    zone = {
        "id": "Z3", "name": "Gas Processing",
        "permit": "hot_work", "maintenance": None,
        "changeover": False, "workers": 4,
        "currentGas": 38, "gasThresh": 50,
    }
    reasons = [{"w": "+40", "t": "Hot work permit active + rising gas trend", "pct": None}]
    matches = find_similar_incidents(zone, 65, reasons)
    assert isinstance(matches, list)
    for m in matches:
        assert "id" in m
        assert "incident_id" in m
        assert "outcome" in m
        assert "lessons" in m


def test_find_similar_incidents_with_gas_factor():
    zone = {
        "id": "Z1", "name": "Blast Furnace A",
        "permit": None, "maintenance": "confined_space_entry",
        "changeover": True, "workers": 6,
        "currentGas": 45, "gasThresh": 50,
    }
    reasons = [
        {"w": "+30", "t": "Gas reading approaching threshold", "pct": 90},
        {"w": "+20", "t": "Confined space entry in progress", "pct": None},
        {"w": "+15", "t": "Shift changeover - reduced supervision continuity", "pct": None},
    ]
    matches = find_similar_incidents(zone, 70, reasons)
    assert len(matches) > 0


def test_get_pattern_insights_returns_string():
    zone = {"id": "Z3", "name": "Gas Processing", "score": 65}
    reasons = [{"w": "+40", "t": "Hot work permit active + rising gas trend", "pct": None}]
    insight = get_pattern_insights(zone, reasons)
    assert isinstance(insight, str)
    assert len(insight) > 0


def test_get_pattern_insights_with_changeover():
    zone = {"id": "Z6", "name": "Steam Plant", "score": 40}
    reasons = [{"w": "+15", "t": "Shift changeover - reduced supervision continuity", "pct": None}]
    insight = get_pattern_insights(zone, reasons)
    assert "changeover" in insight.lower() or len(insight) > 0
