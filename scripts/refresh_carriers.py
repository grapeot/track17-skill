#!/usr/bin/env python3
"""Refresh src/track17_skill/carriers.json from the official 17TRACK carrier list.

Source: https://res.17track.net/asset/carrier/info/apicarrier.all.json
(the official URL referenced by API error -18019903). Run occasionally;
the list changes slowly.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from track17_skill.client import CARRIER_CODE_URL  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "src" / "track17_skill" / "carriers.json"


def main() -> int:
    with urllib.request.urlopen(CARRIER_CODE_URL, timeout=60) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    carriers = [
        {
            "code": row["key"],
            "name": row.get("_name") or "",
            "country": row.get("_country_iso") or "",
            "url": row.get("_url") or "",
        }
        for row in rows
        if row.get("key") and row.get("_name")
    ]
    OUT.write_text(json.dumps(carriers, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(carriers)} carriers -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
