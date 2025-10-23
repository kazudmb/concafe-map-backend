import math
import re
import time
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - allow running as script without package context
    from ..util import RobotsGuard
except ImportError:  # pragma: no cover
    from util import RobotsGuard


class ConCafeProvider:
    """Crawler implementation for https://con-cafe.jp/"""

    API_BASE = "https://con-cafe.jp/api"
    START_URL = "https://con-cafe.jp/list"
    PAGE_DELAY = 0.5
    DETAIL_DELAY = 0.2

    DAY_MAP = {
        "MONDAY": "monday",
        "TUESDAY": "tuesday",
        "WEDNESDAY": "wednesday",
        "THURSDAY": "thursday",
        "FRIDAY": "friday",
        "SATURDAY": "saturday",
        "SUNDAY": "sunday",
        "HOLIDAY": "holiday",
        "PRE_HOLIDAY": "pre_holiday",
    }

    def fetch(self, area: str, session) -> List[Dict[str, Any]]:
        guard = RobotsGuard(session, self.START_URL)
        if not guard.allowed(self.START_URL):
            print("robots.txt disallows fetching START_URL; skipping")
            return []

        params = self._build_query(area)
        page = 1
        shops: List[Dict[str, Any]] = []
        total = None
        page_size = None

        while True:
            data = self._fetch_page(session, page, params)
            if not data:
                break

            summaries = data.get("shops", [])
            if not summaries:
                break

            if total is None:
                total = data.get("count", len(summaries))
            if page_size is None:
                page_size = max(len(summaries), 1)

            for summary in summaries:
                shop_id = summary.get("id")
                if not shop_id:
                    continue
                detail = self._fetch_detail(session, shop_id)
                if not detail:
                    continue
                normalized = self._normalize(detail)
                if normalized:
                    shops.append(normalized)
                time.sleep(self.DETAIL_DELAY)

            page += 1
            if total is not None and page_size is not None:
                max_pages = math.ceil(total / page_size)
                if page > max_pages:
                    break

            time.sleep(self.PAGE_DELAY)

        return shops

    def _build_query(self, area: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if area and area not in ("all", "*"):
            parts = [p for p in area.split("/") if p]
            if parts:
                params["region"] = parts[0]
            if len(parts) > 1:
                params["prefecture"] = parts[1]
            if len(parts) > 2:
                params["area"] = parts[2]
        return params

    def _fetch_page(self, session, page: int, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            resp = session.get(f"{self.API_BASE}/shop", params={**params, "page": page})
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Failed to fetch page {page}: {exc}")
            return None

    def _fetch_detail(self, session, shop_id: int) -> Optional[Dict[str, Any]]:
        try:
            resp = session.get(f"{self.API_BASE}/shop/{shop_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Failed to fetch shop {shop_id}: {exc}")
            return None

    def _normalize(self, detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not detail.get("name"):
            return None

        shop_id = detail.get("id")
        pref = (detail.get("prefecture") or {}).get("name")
        raw_address = detail.get("address") or ""
        address = self._merge_address(pref, raw_address)
        postal = self._normalize_postal(detail.get("postalcode"))
        tel = self._normalize_phone(detail.get("tel"))
        lat = self._to_float(detail.get("lat"))
        lng = self._to_float(detail.get("lng"))

        area = detail.get("area") or {}
        region = area.get("region") or {}
        prefecture = detail.get("prefecture") or {}

        source_url = None
        if region.get("slug") and prefecture.get("slug") and area.get("slug") and shop_id:
            source_url = (
                f"https://con-cafe.jp/list/{region['slug']}/{prefecture['slug']}/{area['slug']}/{shop_id}"
            )

        business_hours = self._parse_business_hours(detail.get("new_business_hours") or [])
        concepts = [c.get("concept", {}).get("name") for c in detail.get("concepts", [])]
        tags = [name for name in concepts if name]

        sns = {
            "x": self._clean_url(detail.get("twitter")),
            "instagram": self._clean_url(detail.get("instagram")),
            "tiktok": self._clean_url(detail.get("tiktok")),
            "youtube": self._clean_url(detail.get("youtube")),
            "web": self._clean_url(detail.get("webpage")),
        }
        sns = {k: v for k, v in sns.items() if v}

        nearest = self._split_lines(detail.get("nearest_stations"))
        holidays = self._split_lines(detail.get("holidays"))

        return {
            "id": f"concafe:{shop_id}",
            "name": detail.get("name", "").strip(),
            "area": area.get("name") or region.get("name") or "",
            "address": address,
            "postalCode": postal,
            "phone": tel,
            "lat": lat,
            "lng": lng,
            "nearestStations": nearest,
            "businessHours": business_hours,
            "businessHoursText": detail.get("business_hours") or None,
            "holidays": holidays,
            "tags": tags,
            "sourceUrl": source_url or self.START_URL,
            "googleMapUrl": self._clean_url(detail.get("google_map_url")),
            "sns": sns,
        }

    def _merge_address(self, prefecture: Optional[str], address: str) -> str:
        address = address.strip()
        if prefecture and address and not address.startswith(prefecture):
            return f"{prefecture}{address}"
        if prefecture and not address:
            return prefecture
        return address

    def _normalize_postal(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) == 7:
            return f"{digits[:3]}-{digits[3:]}"
        return value.strip()

    def _normalize_phone(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return value.strip()

    def _parse_business_hours(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for entry in entries:
            day = self.DAY_MAP.get((entry.get("day_type") or "").upper())
            if not day:
                continue
            start = entry.get("start_time") or None
            end = entry.get("end_time") or None
            if start:
                start = start.strip()
            if end:
                end = end.strip()
            normalized.append({
                "day": day,
                "open": start or None,
                "close": end or None,
            })
        return normalized

    def _to_float(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _clean_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        return url.strip()

    def _split_lines(self, value: Optional[str]) -> List[str]:
        if not value:
            return []
        parts = [line.strip() for line in re.split(r"[\r\n]+", value) if line.strip()]
        return parts
