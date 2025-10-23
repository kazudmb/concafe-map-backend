from typing import Any, Dict, List
from bs4 import BeautifulSoup

try:  # pragma: no cover - import fallback for script execution
    from ..util import RobotsGuard
except ImportError:  # pragma: no cover
    from util import RobotsGuard


class ExampleProvider:
    """
    Example provider that demonstrates structure only.
    Replace URL and parsing logic after legal/TOS review.
    """

    START_URL = "https://example.com/shinjuku-concafe-list"  # placeholder

    def fetch(self, area: str, session) -> List[Dict[str, Any]]:
        guard = RobotsGuard(session, self.START_URL)
        if not guard.allowed(self.START_URL):
            print("robots.txt disallows fetching START_URL; skipping")
            return []
        # Example HTML parsing (placeholder)
        resp = session.get(self.START_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        # This block is placeholder. Replace according to actual DOM.
        items = []
        for i, el in enumerate(soup.select(".shop")):
            name = el.select_one(".name").get_text(strip=True)
            lat = float(el.get("data-lat", 35.690921))
            lng = float(el.get("data-lng", 139.700257))
            address = el.select_one(".address").get_text(strip=True) if el.select_one(".address") else ""
            hours = el.select_one(".hours").get_text(strip=True) if el.select_one(".hours") else ""
            items.append({
                "id": f"example:{i}",
                "name": name,
                "area": area,
                "address": address,
                "lat": lat,
                "lng": lng,
                "hours": hours,
                "tags": ["example"],
                "sourceUrl": self.START_URL,
            })
        return items
