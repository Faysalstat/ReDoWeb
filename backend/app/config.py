from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    storage_root: str = "./storage_data"
    max_pages: int = 3
    crawler_user_agent: str = "ReDoWebsBot/0.1 (+https://redowebs.example/bot)"
    request_timeout_seconds: float = 15.0

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_url: str = "https://redowebs.local"
    openrouter_app_name: str = "ReDoWebs"
    vision_model: str = "openai/gpt-4o-mini"

    generation_model: str = "anthropic/claude-sonnet-4.5"
    generation_max_tokens: int = 16000
    generation_max_iterations: int = 24
    generation_max_consecutive_failures: int = 3
    generation_prompt_caching_enabled: bool = True

    vision_max_image_dimension: int = 1024
    vision_max_tokens: int = 1024

    database_url: str = "postgresql+psycopg://redowebs:redowebs@localhost:15432/redowebs"

    celery_broker_url: str = "redis://localhost:6380/0"
    celery_result_backend: str = "redis://localhost:6380/0"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8123/api/v1/auth/google/callback"
    frontend_url: str = "http://localhost:4200"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    rate_limit_auth: str = "10/minute"
    rate_limit_submit: str = "5/minute"

    class Config:
        env_prefix = "REDOWEBS_"
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
