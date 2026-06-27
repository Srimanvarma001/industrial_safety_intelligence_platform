import pytest
import sys
sys.path.insert(0, "backend")

from risk_engine import (
    compute_compound_risk, compute_single_sensor_risk, compute_detection_gap,
    get_risk_label, record_detection_event,
)


def test_low_risk():
    zone = {"id": "Z1", "currentGas": 10, "gasThresh": 50,
            "permit": None, "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [10, 10, 10])
    assert score < 31
    assert get_risk_label(score) == "LOW"


def test_gas_approaching_threshold():
    zone = {"id": "Z1", "currentGas": 45, "gasThresh": 50,
            "permit": None, "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [40, 42, 45])
    assert score >= 30


def test_gas_elevated_but_not_approaching():
    zone = {"id": "Z1", "currentGas": 33, "gasThresh": 50,
            "permit": None, "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [30, 31, 33])
    assert 15 <= score < 30
    assert any("60%" in r["t"] for r in reasons)


def test_hot_work_rising_gas():
    zone = {"id": "Z3", "currentGas": 38, "gasThresh": 50,
            "permit": "hot_work", "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [30, 32, 38])
    assert score >= 55


def test_hot_work_no_rising_gas():
    zone = {"id": "Z3", "currentGas": 30, "gasThresh": 50,
            "permit": "hot_work", "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [30, 30, 30])
    assert score == 15
    assert any("Hot work permit" in r["t"] for r in reasons)


def test_welding_permit():
    zone = {"id": "Z2", "currentGas": 18, "gasThresh": 45,
            "permit": "welding", "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [18, 18, 18])
    assert score == 8


def test_confined_space():
    zone = {"id": "Z1", "currentGas": 10, "gasThresh": 50,
            "permit": None, "maintenance": "confined_space_entry", "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [10, 10, 10])
    assert score == 20


def test_shift_changeover():
    zone = {"id": "Z6", "currentGas": 22, "gasThresh": 50,
            "permit": None, "maintenance": None, "changeover": True, "workers": 2}
    score, reasons = compute_compound_risk(zone, [22, 22, 22])
    assert score == 15


def test_high_worker_density():
    zone = {"id": "Z1", "currentGas": 10, "gasThresh": 50,
            "permit": None, "maintenance": None, "changeover": False, "workers": 6}
    score, reasons = compute_compound_risk(zone, [10, 10, 10])
    assert score == 5


def test_critical_risk_combination():
    zone = {"id": "Z3", "currentGas": 48, "gasThresh": 50,
            "permit": "hot_work", "maintenance": "confined_space_entry",
            "changeover": True, "workers": 6}
    score, reasons = compute_compound_risk(zone, [35, 40, 48])
    assert score >= 61
    assert get_risk_label(score) in ("HIGH", "CRITICAL")


def test_score_capped_at_100():
    zone = {"id": "Z3", "currentGas": 49, "gasThresh": 50,
            "permit": "hot_work", "maintenance": "confined_space_entry",
            "changeover": True, "workers": 8}
    score, reasons = compute_compound_risk(zone, [35, 40, 49])
    assert score <= 100


def test_get_risk_label_boundaries():
    assert get_risk_label(0) == "LOW"
    assert get_risk_label(30) == "LOW"
    assert get_risk_label(31) == "MEDIUM"
    assert get_risk_label(60) == "MEDIUM"
    assert get_risk_label(61) == "HIGH"
    assert get_risk_label(79) == "HIGH"
    assert get_risk_label(80) == "CRITICAL"
    assert get_risk_label(100) == "CRITICAL"


def test_empty_gas_history():
    zone = {"id": "Z1", "currentGas": 10, "gasThresh": 50,
            "permit": None, "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, None)
    assert score < 31
    assert len(reasons) == 0


def test_no_gas_threshold_division_by_zero():
    zone = {"id": "Z1", "currentGas": 10, "gasThresh": 0,
            "permit": None, "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [10, 10, 10])
    assert score == 0


def test_single_sensor_below_threshold():
    zone = {"id": "Z1", "currentGas": 30, "gasThresh": 50}
    score, reasons = compute_single_sensor_risk(zone)
    assert score == 0
    assert len(reasons) == 0


def test_single_sensor_near_threshold():
    zone = {"id": "Z1", "currentGas": 44, "gasThresh": 50}
    score, reasons = compute_single_sensor_risk(zone)
    assert score == 60
    assert any("warning" in r["t"].lower() for r in reasons)


def test_single_sensor_at_threshold():
    zone = {"id": "Z1", "currentGas": 50, "gasThresh": 50}
    score, reasons = compute_single_sensor_risk(zone)
    assert score == 100
    assert any("breached" in r["t"].lower() for r in reasons)


def test_detection_gap_compound_only():
    gap = compute_detection_gap(75, 0)
    assert gap["compound_detected"] is True
    assert gap["single_detected"] is False
    assert gap["compound_only_detection"] is True
    assert gap["gap_size"] == 75


def test_detection_gap_both_detect():
    gap = compute_detection_gap(75, 61)
    assert gap["compound_detected"] is True
    assert gap["single_detected"] is True
    assert gap["compound_only_detection"] is False


def test_detection_gap_neither():
    gap = compute_detection_gap(30, 0)
    assert gap["compound_detected"] is False
    assert gap["single_detected"] is False
    assert gap["compound_only_detection"] is False
    assert gap["gap_size"] == 0


def test_detection_stats_tracking():
    from risk_engine import DETECTION_STATS, reset_detection_stats, get_detection_summary
    reset_detection_stats()
    record_detection_event(75, 0)
    record_detection_event(61, 0)
    record_detection_event(85, 100)
    summary = get_detection_summary()
    assert summary["total_events"] == 3
    assert summary["compound_detections"] == 3
    assert summary["single_sensor_detections"] == 1
    assert summary["compound_only_detections"] == 2
    assert summary["false_negative_rate_compound"] == 0.0
    assert summary["false_negative_rate_single"] == 66.7
    assert summary["fnr_reduction"] == 100.0
