class OpenRouterError(Exception):
    """Raised for any failure calling OpenRouter -- missing API key,
    network failure, or a response that doesn't match the expected shape."""


class BlueprintExtractionError(Exception):
    """Raised when a project's crawl output can't be turned into a
    blueprint (e.g. missing metadata.json, no pages)."""


class GenerationError(Exception):
    """Raised for definitive site-generation failures -- disabled tier,
    missing blueprint, missing API key, or a sandbox path violation from
    the agent's tool calls."""
