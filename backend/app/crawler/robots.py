from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from .errors import SiteInaccessible


def check_robots_allowed(start_url: str, user_agent: str) -> None:
    """Raises SiteInaccessible if robots.txt disallows the crawler on the
    homepage path. A missing/unreachable robots.txt is treated as allow-all,
    per RobotFileParser's default behavior."""
    robots_url = urljoin(start_url, "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        return

    if not parser.can_fetch(user_agent, start_url):
        raise SiteInaccessible("robots.txt disallows crawling this site")
