import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from providers import registry
from util import http_client


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
        out.append({
            "id": c["id"],
            "name": c.get("name", ""),
            "area": c.get("area", area),
            "address": c.get("address", ""),
            "lat": float(c["lat"]),
            "lng": float(c["lng"]),
            "hours": c.get("hours", ""),
            "tags": c.get("tags", []),
            "sourceUrl": c.get("sourceUrl", ""),
            "updatedAt": now,
        })
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

