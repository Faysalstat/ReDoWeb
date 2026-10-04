class OpenRouterError(Exception):
    """Raised for any failure calling OpenRouter -- missing API key,
    network failure, or a response that doesn't match the expected shape."""


class GenerationError(Exception):
    """Raised for definitive generation failures -- missing blueprint,
    missing API key, or a sandbox path violation from the agent's tool
    calls."""
