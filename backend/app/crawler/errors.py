class CrawlError(Exception):
    """Base class for definitive crawl failures -- these are never retried
    and never consume a credit (per docs/implementation-plan.md)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class SiteInaccessible(CrawlError):
    """The site could not be crawled at all: non-200 status, robots.txt
    disallow, or a detected login/auth wall."""


class CrawlRejected(CrawlError):
    """The site is out of scope for v1 -- currently only raised when more
    than the configured max page count is discovered. The whole submission
    is rejected, never silently truncated."""
