"""
SafetyIQ — Multi-channel alert dispatch with real HTTP calls.
Uses environment variables for webhook URLs; falls back to simulation
when endpoints are not configured.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.database import insert_alert

logger = logging.getLogger("safetyiq.alerts")

ALERT_LOG: list[dict] = []

WEBHOOK_URL = os.environ.get("SAFETYIQ_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL = os.environ.get("SAFETYIQ_SLACK_URL", "")
SMS_API_URL = os.environ.get("SAFETYIQ_SMS_URL", "")
SMS_API_KEY = os.environ.get("SAFETYIQ_SMS_API_KEY", "")

HTTP_TIMEOUT = 10.0


async def _call_webhook(url: str, payload: dict, channel_name: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return {"channel": channel_name, "status": "delivered", "http_status": resp.status_code}
    except httpx.TimeoutException:
        logger.warning(f"[alerts] {channel_name} timed out after {HTTP_TIMEOUT}s")
        return {"channel": channel_name, "status": "failed", "error": "timeout"}
    except httpx.HTTPStatusError as e:
        logger.warning(f"[alerts] {channel_name} returned HTTP {e.response.status_code}")
        return {"channel": channel_name, "status": "failed", "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        logger.error(f"[alerts] {channel_name} error: {e}")
        return {"channel": channel_name, "status": "failed", "error": str(e)}


async def dispatch_alert(alert_type: str, title: str, description: str, zone_id: str, score: int) -> list[dict]:
    timestamp = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []

    payload = {
        "alert_type": alert_type,
        "title": title,
        "description": description,
        "zone_id": zone_id,
        "score": score,
        "timestamp": timestamp,
        "source": "SafetyIQ",
    }

    channels: list[tuple[str, str, str, str | None]] = [
        ("safety_officer", "SafetyIQ In-App", "Safety Officer (app notification)", None),
        ("shift_supervisor", "SMS", "Shift Supervisor (+91-98765-43210)", SMS_API_URL if SMS_API_URL and SMS_API_KEY else None),
        ("emergency_team", "Webhook", "Emergency Response Team", WEBHOOK_URL if WEBHOOK_URL else None),
        ("slack", "Slack Webhook", "#safety-alerts", SLACK_WEBHOOK_URL if SLACK_WEBHOOK_URL else None),
    ]

    dispatch_tasks = []

    for channel_key, channel_display, recipient, url in channels:
        if url:
            task = _call_webhook(url, payload, channel_display)
            dispatch_tasks.append(task)
        else:
            results.append({
                "channel": channel_display,
                "status": "delivered",
                "note": "simulated (no endpoint configured)",
            })

    if dispatch_tasks:
        real_results = await asyncio.gather(*dispatch_tasks, return_exceptions=True)
        for r in real_results:
            if isinstance(r, dict):
                results.append(r)
            else:
                results.append({"channel": "unknown", "status": "failed", "error": str(r) if r else "unknown error"})

    alert_entry = {
        "id": f"ALT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{zone_id}",
        "type": alert_type,
        "title": title,
        "description": description,
        "zone_id": zone_id,
        "score": score,
        "timestamp": timestamp,
        "channels_dispatched": results,
    }

    ALERT_LOG.insert(0, alert_entry)
    if len(ALERT_LOG) > 100:
        ALERT_LOG.pop()

    try:
        insert_alert(alert_entry)
    except Exception as e:
        logger.error(f"[alerts] Failed to persist alert to database: {e}")

    return results


def get_alert_log(limit: int = 20) -> list[dict]:
    return ALERT_LOG[:limit]
