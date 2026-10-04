from app.ai.errors import GenerationError
from app.ai.openrouter_client import OpenRouterError
from app.crawler.errors import CrawlRejected, SiteInaccessible
from app.errors import user_facing_message
from app.services.storage_capacity_service import InsufficientDiskSpaceError
from app.services.wallet_service import InsufficientCreditsError

FALLBACK = "Something went wrong. Please try again."


def test_known_error_types_pass_through_their_own_message():
    for exc in (
        SiteInaccessible("this site blocked automated access"),
        CrawlRejected("site has too many pages"),
        GenerationError("no blueprint found for this project"),
        InsufficientCreditsError("insufficient credits"),
        InsufficientDiskSpaceError("not enough free disk space"),
    ):
        assert user_facing_message(exc, FALLBACK) == str(exc)


def test_openrouter_error_falls_back_instead_of_leaking_its_raw_body():
    exc = OpenRouterError("Unexpected OpenRouter response shape: {'choices': [...massive raw json...]}")
    assert user_facing_message(exc, FALLBACK) == FALLBACK


def test_unexpected_exception_falls_back():
    assert user_facing_message(KeyError("some_internal_field"), FALLBACK) == FALLBACK
