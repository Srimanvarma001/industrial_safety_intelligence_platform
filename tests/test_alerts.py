import pytest
import sys
sys.path.insert(0, "backend")

from alerts import dispatch_alert, get_alert_log, ALERT_LOG
from database import init_db, close_db


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield
    close_db()


@pytest.fixture(autouse=True)
def clear_alert_log():
    ALERT_LOG.clear()
    yield
    ALERT_LOG.clear()


@pytest.mark.asyncio
async def test_dispatch_alert_returns_results():
    results = await dispatch_alert("red", "Test alert", "Test description", "Z1", 85)
    assert len(results) == 4
    for r in results:
        assert "channel" in r
        assert "status" in r


@pytest.mark.asyncio
async def test_dispatch_alert_simulated_delivery():
    results = await dispatch_alert("red", "Test", "Desc", "Z1", 50)
    assert all(r["status"] == "delivered" for r in results)


@pytest.mark.asyncio
async def test_alert_logged():
    await dispatch_alert("yellow", "Warning", "Gas rising", "Z2", 45)
    log = get_alert_log()
    assert len(log) == 1
    assert log[0]["title"] == "Warning"
    assert log[0]["zone_id"] == "Z2"
    assert log[0]["score"] == 45


@pytest.mark.asyncio
async def test_alert_log_limit():
    for i in range(150):
        await dispatch_alert("green", f"Alert {i}", f"Desc {i}", "Z1", 10)
    log = get_alert_log()
    assert len(log) <= 100


@pytest.mark.asyncio
async def test_alert_entry_structure():
    await dispatch_alert("red", "Critical", "High gas", "Z3", 92)
    entry = get_alert_log(1)[0]
    assert "id" in entry
    assert entry["type"] == "red"
    assert entry["zone_id"] == "Z3"
    assert entry["score"] == 92
    assert "timestamp" in entry
    assert len(entry["channels_dispatched"]) == 4
