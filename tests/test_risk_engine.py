import sys
sys.path.insert(0, "backend")

from risk_engine import compute_compound_risk, get_risk_label


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


def test_hot_work_rising_gas():
    zone = {"id": "Z3", "currentGas": 38, "gasThresh": 50,
            "permit": "hot_work", "maintenance": None, "changeover": False, "workers": 2}
    score, reasons = compute_compound_risk(zone, [30, 32, 38])
    assert score >= 55  # 30 (gas elevated) + 40 (hot work + rising)


def test_critical_risk():
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


def test_get_risk_label():
    assert get_risk_label(0) == "LOW"
    assert get_risk_label(30) == "LOW"
    assert get_risk_label(31) == "MEDIUM"
    assert get_risk_label(60) == "MEDIUM"
    assert get_risk_label(61) == "HIGH"
    assert get_risk_label(80) == "CRITICAL"
    assert get_risk_label(100) == "CRITICAL"


if __name__ == "__main__":
    test_low_risk()
    test_gas_approaching_threshold()
    test_hot_work_rising_gas()
    test_critical_risk()
    test_score_capped_at_100()
    test_get_risk_label()
    print("All risk engine tests passed!")
