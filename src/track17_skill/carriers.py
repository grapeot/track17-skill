"""Offline carrier-code lookup backed by the official 17TRACK carrier list.

carriers.json is a snapshot of the official list at
https://res.17track.net/asset/carrier/info/apicarrier.all.json
(the URL that API error -18019903 points to). Regenerate with:

    scripts/refresh_carriers.py
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).parent / "carriers.json"
_cache = None


def _load() -> list:
    global _cache
    if _cache is None:
        _cache = json.loads(_DATA.read_text(encoding="utf-8"))
    return _cache


def search(query: str, limit: int = 10) -> list:
    """Case-insensitive substring match on the carrier name."""
    q = query.lower()
    return [c for c in _load() if q in c["name"].lower()][:limit]


def by_code(code: int):
    for c in _load():
        if c["code"] == code:
            return c
    return None


def count() -> int:
    return len(_load())
