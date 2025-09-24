from urllib.parse import urlparse
from urllib import robotparser
import requests


def http_client(user_agent: str):
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    s.timeout = 20
    return s


class RobotsGuard:
    def __init__(self, session: requests.Session, url: str):
        self.session = session
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self.rp = robotparser.RobotFileParser()
        try:
            r = session.get(robots_url)
            if r.status_code == 200:
                self.rp.parse(r.text.splitlines())
            else:
                # If robots is missing, be conservative but allow by default
                self.rp = None
        except Exception:
            self.rp = None

    def allowed(self, url: str) -> bool:
        if self.rp is None:
            return True
        return self.rp.can_fetch(self.session.headers.get("User-Agent", "*"), url)

