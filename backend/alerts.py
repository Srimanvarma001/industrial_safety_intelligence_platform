import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("safetyiq.alerts")


ALERT_LOG: list[dict] = []


async def dispatch_alert(alert_type: str, title: str, description: str, zone_id: str, score: int) -> list[dict]:
    timestamp = datetime.now(timezone.utc).isoformat()
    results = []

    channels = {
        "safety_officer": {
            "channel": "SafetyIQ In-App",
            "recipient": "Safety Officer (app notification)",
            "success": True
        },
        "shift_supervisor": {
            "channel": "SMS (simulated)",
            "recipient": "Shift Supervisor (+91-98765-43210)",
            "success": True
        },
        "emergency_team": {
            "channel": "Webhook",
            "recipient": "Emergency Response Team (https://hooks.safetyiq.internal/ert)",
            "success": True
        },
        "slack": {
            "channel": "Slack Webhook",
            "recipient": "#safety-alerts channel",
            "success": True
        }
    }

    alert_entry = {
        "id": f"ALT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{zone_id}",
        "type": alert_type,
        "title": title,
        "description": description,
        "zone_id": zone_id,
        "score": score,
        "timestamp": timestamp,
        "channels_dispatched": []
    }

    for channel_key, channel_info in channels.items():
        try:
            if channel_key in ("slack", "emergency_team"):
                webhook_result = await _send_webhook(channel_info["recipient"], title, description, zone_id, score)
                status = "delivered" if webhook_result else "failed"
            else:
                status = "delivered"
            alert_entry["channels_dispatched"].append({
                "channel": channel_info["channel"],
                "recipient": channel_info["recipient"],
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            results.append({"channel": channel_info["channel"], "status": status})
        except Exception as e:
            logger.error(f"Failed to dispatch alert via {channel_key}: {e}")
            results.append({"channel": channel_info["channel"], "status": "failed", "error": str(e)})

    ALERT_LOG.insert(0, alert_entry)
    if len(ALERT_LOG) > 100:
        ALERT_LOG.pop()

    return results


async def _send_webhook(url: str, title: str, description: str, zone_id: str, score: int) -> bool:
    try:
        import httpx
        payload = {
            "event": "compound_risk_alert",
            "title": title,
            "description": description,
            "zone_id": zone_id,
            "score": score,
            "severity": "critical" if score >= 80 else "high",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code < 500
    except Exception:
        return False


def get_alert_log(limit: int = 20) -> list[dict]:
    return ALERT_LOG[:limit]
