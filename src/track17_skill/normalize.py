"""Normalize 17TRACK v2.4 responses into a stable agent-facing summary.

The v2.4 gettrackinfo response buries the useful fields: latest_status
lives under data.accepted[].track_info (not at the top level of the
accepted item), time_raw is an object {date, time, timezone} rather than
a string, and provider is a nested object. This module flattens exactly
that, so callers never have to re-learn the raw layout.
"""
from __future__ import annotations

MAX_EVENTS = 15


def _loc_text(loc) -> str:
    if not isinstance(loc, dict):
        return ""
    return ", ".join(str(loc[k]) for k in ("city", "state") if loc.get(k)).strip()


def _time_text(event: dict):
    t = event.get("time_raw")
    if isinstance(t, dict):
        return f"{t.get('date') or ''} {t.get('time') or ''}".strip()
    return t or event.get("time_iso")


def _events_from_provider(provider: dict) -> list:
    events = []
    for e in provider.get("events") or []:
        events.append(
            {
                "time": _time_text(e),
                "description": e.get("description") or "",
                "location": _loc_text(e.get("location") or e.get("address")),
            }
        )
    # Carriers return events oldest-first; newest-first is more useful.
    events.reverse()
    return events


def summarize_gettrackinfo(response: dict, max_events: int = MAX_EVENTS) -> dict:
    """Return {"summary": dict | None, "rejected": [...]}.

    summary is None when the number was rejected (see the rejected list
    for error codes).
    """
    data = response.get("data") or {}
    accepted = data.get("accepted") or []
    rejected = data.get("rejected") or []
    if not accepted:
        return {"summary": None, "rejected": rejected}
    a = accepted[0]
    ti = a.get("track_info") or {}
    latest = ti.get("latest_status") or a.get("latest_status") or {}
    ships = ti.get("shipping_info") or {}
    shipper = ships.get("shipper_address") or {}
    recipient = ships.get("recipient_address") or {}
    misc = ti.get("misc_info") or {}
    metrics = ti.get("time_metrics") or {}
    providers = (ti.get("tracking") or {}).get("providers") or []

    events, total, tips, name, service = [], 0, None, None, None
    for prov in providers:
        name = name or (prov.get("provider") or {}).get("name")
        tips = tips or prov.get("provider_tips")
        service = service or prov.get("service_type")
        prov_events = _events_from_provider(prov)
        total += len(prov_events)
        events.extend(prov_events)
    events = events[:max_events]

    summary = {
        "number": a.get("number"),
        "carrier": {"code": a.get("carrier"), "name": name},
        "status": latest.get("status"),
        "sub_status": latest.get("sub_status"),
        "service_type": service or misc.get("service_type"),
        "weight_kg": misc.get("weight_kg"),
        "route": {
            "origin": _loc_text(shipper),
            "destination": _loc_text(recipient),
        },
        "latest_event": events[0] if events else None,
        "days_since_last_update": metrics.get("days_after_last_update"),
        "provider_tips": tips,
        "event_count": total,
        "events": events,
    }
    return {"summary": summary, "rejected": rejected}


def summarize_gettracklist(response: dict, max_items: int = 40) -> dict:
    data = response.get("data") or {}
    accepted = (data.get("accepted") or [])[:max_items]
    items = [
        {
            "number": a.get("number"),
            "carrier_code": a.get("carrier"),
            "status": a.get("status"),
            "sub_status": a.get("sub_status"),
            "sync_status": a.get("sync_status"),
        }
        for a in accepted
    ]
    return {"count": len(accepted), "items": items, "rejected": data.get("rejected") or []}


def summarize_register(response: dict) -> dict:
    data = response.get("data") or {}
    return {"accepted": data.get("accepted") or [], "rejected": data.get("rejected") or []}
