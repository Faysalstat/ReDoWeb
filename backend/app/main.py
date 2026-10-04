from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .logging_config import configure_logging
from .rate_limit import limiter
from .routers import admin, auth, blueprint, crawl, credits, debug_pipeline, downloads, generation, preview, projects

configure_logging()

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
)

app.include_router(auth.router)
app.include_router(credits.router)
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
