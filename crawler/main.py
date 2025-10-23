import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

try:  # pragma: no cover - support running as module or script
    from providers import registry  # type: ignore
    from util import http_client  # type: ignore
except ImportError:  # pragma: no cover
    from .providers import registry
    from .util import http_client


def run(provider: str, area: str) -> List[Dict[str, Any]]:
    if provider not in registry:
        raise SystemExit(f"Unknown provider: {provider}")
    prov = registry[provider]()
    session = http_client(user_agent="concafe-map-crawler/0.1")
    cafes = prov.fetch(area=area, session=session)
    # Minimal normalization
    out: List[Dict[str, Any]] = []
    now = int(time.time())
    for c in cafes:
        lat_val = c.get("lat")
        lng_val = c.get("lng")
        try:
            lat = float(lat_val) if lat_val is not None else None
        except (TypeError, ValueError):
            lat = None
        try:
            lng = float(lng_val) if lng_val is not None else None
        except (TypeError, ValueError):
            lng = None

        item: Dict[str, Any] = {
            "id": c["id"],
            "name": c.get("name", ""),
            "area": c.get("area", area),
            "address": c.get("address", ""),
            "lat": lat,
            "lng": lng,
            "tags": c.get("tags", []),
            "sourceUrl": c.get("sourceUrl", ""),
            "updatedAt": now,
        }

        for key in (
            "postalCode",
            "phone",
            "nearestStations",
            "businessHours",
            "businessHoursText",
            "holidays",
            "sns",
            "googleMapUrl",
        ):
            if key in c and c[key]:
                item[key] = c[key]

        # backwards compatibility with older providers using "hours"
        if "hours" in c and c.get("hours"):
            item["businessHoursText"] = item.get("businessHoursText") or c["hours"]

        out.append(item)

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, help="provider key, e.g., example")
    ap.add_argument("--area", default="shinjuku")
    ap.add_argument("--out", default="cafes.json")
    args = ap.parse_args()

    data = run(args.provider, args.area)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(data)} cafes to {args.out}")


if __name__ == "__main__":
    main()
