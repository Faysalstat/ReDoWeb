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


class IterationLimitError(GenerationError):
    """The agent loop used its whole step budget without finishing. Still a
    GenerationError (generation callers treat it as a failure, as before),
    but it carries what was spent, so a caller whose partial work is still
    useful -- the SEO pass, which edits files in place -- can keep it."""

    def __init__(self, message: str, *, usage: dict, iterations: int, last_content: str = ""):
        super().__init__(message)
        self.usage = usage
        self.iterations = iterations
        self.last_content = last_content
