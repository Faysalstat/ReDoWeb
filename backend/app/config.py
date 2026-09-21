from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    storage_root: str = "./storage_data"
    # Rejects new work outright rather than silently running out of disk
    # mid-generation -- see storage_capacity_service.check_free_disk_space().
    min_free_disk_gb: float = 2.0
    # Raised 5 -> 20, 2026-09-17, at the user's explicit request (CLAUDE.md's
    # "settled decisions" previously said 3 while this was already 5 -- both
    # now reconciled to 20). Sites over this are still rejected outright, not
    # truncated -- see crawler/discover.py. Blueprint AI-review and initial
    # generation still only ever consider the home page; the rest of a
    # multi-page crawl is reviewed/built lazily on first download/purchase
    # (see workers/tasks_full_site.py).
    max_pages: int = 20
    crawler_user_agent: str = "ReDoWebsBot/0.1 (+https://redowebs.example/bot)"
    request_timeout_seconds: float = 15.0

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_url: str = "https://redowebs.local"
    openrouter_app_name: str = "ReDoWebs"
    vision_model: str = "deepseek/deepseek-v4-flash-vision-exp"

    generation_model: str = "deepseek/deepseek-v4.1-flash"
    generation_max_tokens: int = 16000
    generation_max_iterations: int = 24
    generation_max_consecutive_failures: int = 5
    generation_prompt_caching_enabled: bool = True
    # Per-call (one loop iteration, not total generation time) OpenRouter
    # request budget. 6 minutes covers a legitimately slow full-page
    # completion at max_tokens with room to spare, while still bounding how
    # long one stalled call can block the single-threaded queue worker (see
    # openrouter_client._post_with_hard_deadline's extra +30s backstop on
    # top of this). Raised 2026-09-16 from 180s after two real
    # moonshotai/kimi-k2.6 stalls -- both were genuinely dead connections
    # (zero further response, ever), not slow-but-progressing calls, so
    # this bump is about not cutting off a legitimately slow model
    # mid-response, not about "rescuing" a stalled one.
    generation_call_timeout_seconds: float = 360.0

    vision_max_image_dimension: int = 1024
    vision_max_tokens: int = 2048

    # Shared Postgres instance (G:\Standalone Services\postgres, port 5432)
    # used by every project on this machine -- see init/01-init-databases.sh
    # there for the `redowebs` role/database provisioning. This project's
    # own standalone/docker-compose.yml Postgres container is deprecated.
    database_url: str = "postgresql+psycopg://redowebs:redowebs@localhost:5432/redowebs"
    # Shared instance's max_connections is Postgres's default 100, split
    # across 4 other unrelated apps too -- this process's budget is sized so
    # 1 web process + up to 4 queue workers (see queue_worker.py) stays at
    # roughly pool_size+max_overflow=10 each, ~50 total, well under 100. A
    # short pool_timeout makes pool starvation fail fast and visibly rather
    # than silently stalling a request for the SQLAlchemy default 30s.
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 10

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
