# Deploying to Railway

Step-by-step deployment of the backend (API + queue worker), Postgres, and
the Angular frontend to [Railway](https://railway.com). Added 2026-10-03.
For the generic Docker Compose/VPS path see [DOCKER.md](DOCKER.md); local
dev is unchanged ([INSTALLATION.md](INSTALLATION.md)).

## Plan choice

| Plan | Cost | Per-service limits | Fit |
|---|---|---|---|
| Trial | $5 one-time credit | 1 GB RAM, 0.5 GB volume | Testing only |
| Free | $0 (small monthly credit) | 0.5 GB RAM, 0.5 GB volume | Too small: 3 always-on services, and crawl/generated output fills 0.5 GB fast |
| Hobby | $5/mo incl. $5 usage | up to 48 GB RAM, 5 GB volume | Real use |

Limits as of 2026-10 — check https://docs.railway.com/reference/pricing/plans.

## Railway layout (3 services in one project)

| Service | Source | Notes |
|---|---|---|
| `Postgres` | Railway's PostgreSQL template | Managed DB |
| backend | repo, root dir `/backend`, built from `backend/Dockerfile` | Runs **API + queue worker in one container** via `start.sh`; volume at `/app/storage_data` |
| frontend | repo, root dir `/frontend` | `ng build` output served by `npx serve -s` |

**Why API and worker share one service:** Railway allows only one volume per
service and a volume can't be shared across services, but the worker writes
generated output that the API serves via `/preview` (and both read
`storage_data/`). Consequences:

- Only one worker process. Don't enable Railway replicas — services with a
  volume can't have them anyway.
- Redeploys have a few seconds of downtime (a volume can't be mounted by two
  deployments at once).
- **Admin-uploaded prompt templates are not persistent**: they're written to
  `/app/prompts` (`site_generator.PROMPTS_DIR`), which is baked into the image,
  not on the volume — they vanish on every redeploy. The hand-authored
  templates committed to `backend/prompts/` are unaffected. Fixing this would
  mean making `PROMPTS_DIR` configurable and pointing it inside the volume.

## Steps

### 1. Project + database
1. Sign up at railway.com with GitHub.
2. **New Project → Deploy PostgreSQL**.
3. **+ Create → GitHub Repo** → `Faysalstat/ReDoWeb` (this becomes the backend service).

### 2. Backend service settings
- **Source → Root Directory:** `/backend` · **Branch:** the branch you pushed
- **Deploy → Pre-deploy Command:** `alembic upgrade head`
- **Deploy → Custom Start Command:** `bash start.sh`
- **Networking → Generate Domain** (port: Railway injects `$PORT`; `start.sh` binds to it, falling back to 8123)
- Right-click service → **Attach Volume**, mount path `/app/storage_data`

### 3. Backend variables (Variables → Raw Editor)
```
REDOWEBS_DATABASE_URL=postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
REDOWEBS_STORAGE_ROOT=/app/storage_data
REDOWEBS_MIN_FREE_DISK_GB=0.1
REDOWEBS_OPENROUTER_API_KEY=<key>
REDOWEBS_GOOGLE_CLIENT_ID=<client id>
REDOWEBS_GOOGLE_CLIENT_SECRET=<client secret>
REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI=https://<backend-domain>/api/v1/auth/google/callback
REDOWEBS_FRONTEND_URL=https://<frontend-domain>
REDOWEBS_JWT_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
RAILWAY_RUN_UID=0
```
- The `postgresql+psycopg://` prefix is required — Railway's own `DATABASE_URL` uses `postgresql://`, which picks the wrong SQLAlchemy driver.
- `REDOWEBS_MIN_FREE_DISK_GB`: the default (2.0) exceeds a Trial volume and would reject every submission. On Hobby (5 GB) raise to ~1.
- `RAILWAY_RUN_UID=0`: the Dockerfile runs as non-root `appuser`, which can't write to Railway volumes otherwise.
- `REDOWEBS_FRONTEND_URL` also drives the CORS allow-list (`main.py`).

Check: `https://<backend-domain>/health` → `{"status":"ok"}`.

### 4. Frontend service
1. **Before deploying**, set `DEPLOYED_API_BASE_URL` in
   `frontend/src/app/core/api-config.ts` to the backend domain from step 2, commit, push.
2. **+ Create → GitHub Repo** (same repo).
3. **Root Directory:** `/frontend` · **Build Command:** `npm run build` ·
   **Start Command:** `npx serve -s dist/frontend/browser -l $PORT`
   (`-s` = SPA fallback, so deep links like `/history` and `/admin` work on reload).
4. **Networking → Generate Domain** → copy it into the backend's `REDOWEBS_FRONTEND_URL`.

### 5. Google OAuth (Google Cloud Console → Credentials → the OAuth client)
- Authorized redirect URI: `https://<backend-domain>/api/v1/auth/google/callback`
- Authorized JavaScript origin: `https://<frontend-domain>`

### 6. Promote yourself to admin
Sign in once on the deployed site, then from your machine using the Postgres
service's `DATABASE_PUBLIC_URL` (with `postgresql://` → `postgresql+psycopg://`):
```powershell
cd "G:\Current Works\ReDoWebs\backend"
$env:REDOWEBS_DATABASE_URL = "postgresql+psycopg://..."
python -m scripts.promote_admin you@example.com
```

### 7. Smoke test
Submit a small site and watch backend **Deployments → Logs** (API and worker
logs are interleaved there).

## Operating notes
- Pushing to the configured branch auto-redeploys.
- Set a spend cap under **Workspace → Usage**.
- If either the API or the worker dies, `start.sh` stops the other and exits
  non-zero so Railway restarts the whole container (container-level restart
  only — the app's task-level no-auto-retry policy is unchanged).

## Code changes made for this deployment (2026-10-03)

| File | Change |
|---|---|
| `backend/start.sh` (new) | Runs queue worker + uvicorn (`$PORT`) in one container; stops both if either exits. Railway-only, opt-in via start command. |
| `backend/.gitattributes` (new) | Forces LF for `*.sh` (Windows `core.autocrlf=true` would break the script in Linux). |
| `backend/Dockerfile` | `COPY start.sh .` — default `CMD` (uvicorn only) unchanged, so both compose files behave as before. |
| `backend/app/main.py` | CORS allows `http://localhost:4200` **plus** `settings.frontend_url` (was hardcoded localhost only). |
| `frontend/src/app/core/api-config.ts` | Uses `http://localhost:8123` on localhost/127.0.0.1, otherwise `DEPLOYED_API_BASE_URL` (placeholder — must be filled in). |
| `.gitignore` (new, repo root) | Ignores `clients/` (Google OAuth client-secret downloads). |
| `clients/client_secret_…json` | Untracked via `git rm --cached` (file kept on disk). It was previously committed and pushed — **rotate the client secret in Google Cloud Console** if the repo was ever public. |
