from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# backend/standalone_agents/landing_agent/ (the app root -- one level above
# this package), where skill.md, .env, requirements.txt, and content/ live.
APP_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = APP_ROOT / "skill.md"
CONTENT_DIR = APP_ROOT / "content"


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_url: str = "https://landing-agent.local"
    openrouter_app_name: str = "LandingPageAgent"

    generation_model: str = "anthropic/claude-opus-5"
    generation_max_tokens: int = 16000
    generation_max_iterations: int = 24
    generation_max_consecutive_failures: int = 5
    generation_prompt_caching_enabled: bool = True

    class Config:
        env_prefix = "LANDING_AGENT_"
        env_file = str(APP_ROOT / ".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
