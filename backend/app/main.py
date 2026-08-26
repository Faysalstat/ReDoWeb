from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .rate_limit import limiter
from .routers import admin, auth, blueprint, crawl, credits, downloads, generation, preview, projects

app = FastAPI(title="ReDoWebs API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
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


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
