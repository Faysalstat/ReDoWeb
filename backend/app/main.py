from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .logging_config import configure_logging
from .observability.middleware import RequestContextMiddleware
from .rate_limit import limiter
from .routers import (
    admin,
    auth,
    billing,
    blueprint,
    crawl,
    credits,
    debug_pipeline,
    downloads,
    generation,
    preview,
    projects,
    tiers,
)

configure_logging(service="api")

app = FastAPI(title="ReDoWebs API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    # Local dev origin always allowed; the deployed frontend comes from
    # REDOWEBS_FRONTEND_URL (trailing slash stripped -- browsers send Origin
    # without one, and CORS matches exactly).
    allow_origins=sorted({"http://localhost:4200", get_settings().frontend_url.rstrip("/")}),
    allow_credentials=True,  # required so the refresh-token httpOnly cookie is sent cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the frontend read the id it can show a user as an error reference.
    expose_headers=["X-Request-ID"],
)
# Added last so it's the outermost layer: every request, including CORS
# preflights and errors raised by the layers inside it, gets a request id
# and one http.request log line.
app.add_middleware(RequestContextMiddleware)

app.include_router(auth.router)
app.include_router(credits.router)
app.include_router(billing.router)
app.include_router(tiers.router)
app.include_router(crawl.router)
app.include_router(blueprint.router)
app.include_router(generation.router)
app.include_router(projects.router)
app.include_router(downloads.router)
app.include_router(preview.router)
app.include_router(admin.router)
app.include_router(debug_pipeline.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
