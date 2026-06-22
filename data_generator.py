"""
SafetyIQ — Synthetic Data Generator
Generates realistic industrial sensor event streams and scenario injections.
"""

import json
import random
import time
from datetime import datetime, timezone
from typing import Any


ZONES = [
    {"id": "Z1", "name": "Blast Furnace A", "gasThresh": 50},
    {"id": "Z2", "name": "Coke Oven Bay", "gasThresh": 45},
    {"id": "Z3", "name": "Gas Processing", "gasThresh": 50},
    {"id": "Z4", "name": "Ore Handling", "gasThresh": 60},
    {"id": "Z5", "name": "Slag Yard", "gasThresh": 60},
    {"id": "Z6", "name": "Steam Plant", "gasThresh": 50},
    {"id": "Z7", "name": "Cooling Tower", "gasThresh": 45},
    {"id": "Z8", "name": "Control Room", "gasThresh": 30},
]

BASE_GAS: dict[str, float] = {
    "Z1": 28, "Z2": 18, "Z3": 35, "Z4": 12,
    "Z5": 8,  "Z6": 22, "Z7": 5,  "Z8": 2,
}

current_gas: dict[str, float] = dict(BASE_GAS)
scenario_active = False
step = 0


def generate_gas_reading(zone: dict) -> dict:
    zid = zone["id"]
    base = current_gas[zid]
    noise = (random.random() - 0.5) * 4
    ppm = max(0, round(base + noise, 1))
    current_gas[zid] = ppm

    return {
        "event_type": "gas_reading",
        "zone_id": zid,
        "zone_name": zone["name"],
        "gas_type": "CO",
        "ppm": ppm,
        "threshold_ppm": zone["gasThresh"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def generate_permit_event(zone_id: str, permit_type: str, status: str = "active") -> dict:
    permit_id = f"PTW-{random.randint(1000, 9999)}"
    return {
        "event_type": "permit",
        "permit_id": permit_id,
        "permit_type": permit_type,
        "zone_id": zone_id,
        "status": status,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": datetime.now(timezone.utc).isoformat()
    }


def generate_maintenance_event(zone_id: str, activity: str, status: str = "in_progress") -> dict:
    return {
        "event_type": "maintenance",
        "zone_id": zone_id,
        "activity": activity,
        "status": status,
        "crew_size": random.randint(2, 4),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def generate_shift_changeover(zone_id: str) -> dict:
    return {
        "event_type": "shift_changeover",
        "zone_id": zone_id,
        "window_start": datetime.now(timezone.utc).isoformat(),
        "window_end": datetime.now(timezone.utc).isoformat()
    }


def generate_worker_location(zone_id: str, worker_count: int) -> list[dict]:
    events = []
    for i in range(worker_count):
        wid = f"W-{100 + int(zone_id[1:]) * 10 + i}"
        events.append({
            "event_type": "worker_location",
            "worker_id": wid,
            "zone_id": zone_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    return events


def run_vizag_scenario():
    global scenario_active, step, current_gas

    scenario_active = True
    step = 0
    print("[Scenario] Triggering Vizag scenario on Z3...")
    z3_gas = current_gas["Z3"]

    steps = [
        lambda: print("[Scenario] Step 1: Hot work permit issued"),
        lambda: set_gas("Z3", 38),
        lambda: set_gas("Z3", 41),
        lambda: print("[Scenario] Step 3: Maintenance crew enters confined space"),
        lambda: set_gas("Z3", 44),
        lambda: set_gas("Z3", 46),
        lambda: print("[Scenario] Step 5: Shift changeover window"),
        lambda: set_gas("Z3", 48),
        lambda: print("[Scenario] Step 6: Compound risk threshold breached"),
    ]

    for fn in steps:
        fn()
        time.sleep(2)
        for zone in ZONES:
            event = generate_gas_reading(zone)
            yield event

    scenario_active = False
    print("[Scenario] Complete")


def set_gas(zid: str, val: float):
    current_gas[zid] = val


def run(interval: float = 2.0, scenario_after: int | None = None):
    print(f"[Generator] Starting data stream (interval={interval}s)")
    if scenario_after:
        print(f"[Generator] Will trigger Vizag scenario after {scenario_after} ticks")

    ticks = 0
    try:
        for zone in ZONES:
            for evt in generate_worker_location(zone["id"], 2):
                yield evt

        while True:
            for zone in ZONES:
                yield generate_gas_reading(zone)

            ticks += 1
            if scenario_after and ticks == scenario_after:
                for evt in run_vizag_scenario():
                    yield evt

            if ticks % 10 == 0:
                zid = random.choice(ZONES)["id"]
                yield generate_permit_event(zid, random.choice(["hot_work", "welding", "none"]))

            if ticks % 15 == 0:
                zid = random.choice(ZONES)["id"]
                yield generate_maintenance_event(zid, "confined_space_entry")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("[Generator] Stopped")


if __name__ == "__main__":
    import sys

    output_mode = sys.argv[1] if len(sys.argv) > 1 else "stdout"

    if output_mode == "api":
        import httpx

        def send_to_api(client: httpx.Client, events: list[dict]):
            for evt in events:
                try:
                    if evt["event_type"] == "gas_reading":
                        client.post(f"/api/zones/{evt['zone_id']}/update", json={"gas": evt["ppm"]})
                except Exception as e:
                    print(f"[Generator] API error: {e}")

        batch: list[dict] = []
        with httpx.Client(base_url="http://localhost:8000") as client:
            for evt in run(interval=2.0):
                batch.append(evt)
                if len(batch) >= 8:
                    send_to_api(client, batch)
                    batch = []
    else:
        for evt in run(interval=2.0):
            print(json.dumps(evt))
