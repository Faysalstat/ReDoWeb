# Dockerizing the backend (local + cloud)

This covers running the **backend only** — the FastAPI API process and the
Postgres-backed queue worker (`app/workers/queue_worker.py`) — in Docker.
The frontend (Angular) is not containerized here; it keeps running via
`npm start` per [INSTALLATION.md](INSTALLATION.md), pointed at whichever
backend URL you bring up below.

Both processes come from the **same image** (`backend/Dockerfile`) — which
one runs is decided by the `command:` a compose file passes in, not by the
image itself. There's also a one-shot `migrate` service (`alembic upgrade
head`) that runs once before `api`/`worker` start, in both compose files
below.

## Files

- `backend/Dockerfile` — the image (Python 3.12-slim, non-root user, `app/` + `alembic/` + `prompts/` baked in).
- `backend/.dockerignore` — keeps `venv/`, `.env`, logs, `storage_data/`, tests, and the unrelated `standalone_agents/` scratch folder out of the build context.
- `standalone/docker-compose.backend.local.yml` — local testing, per this repo's mandated Compose-files-live-in-`standalone/` layout ([rule.md](../rule.md)).
- `standalone/docker-compose.backend.yml` — generic cloud/VPS deployment (self-contained, bundles its own Postgres).

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + the Compose plugin (Linux) — `docker compose version` should report v2.x.
- For local testing: the existing shared Postgres container already running on this machine (`G:\Standalone Services\postgres` → `docker compose up -d` there), and `backend/.env` already filled in per [INSTALLATION.md](INSTALLATION.md) section 2.2.

**This is a testing/deployment path for the containerized artifact, not a
replacement for day-to-day dev** — there's no live-reload bind mount, so
code edits require a rebuild (`--build`). Keep using the venv +
`uvicorn --reload` flow from INSTALLATION.md for routine backend
development.

## Local (Docker Desktop, connects to the existing shared Postgres)

Per your setup, the containerized backend talks to the same shared
Postgres container everything else on this machine already uses
(`localhost:5432` from the host) — not a Postgres-in-Compose. Docker
Desktop exposes the host as `host.docker.internal` from inside a
container, which the local compose file uses instead of `localhost`.

```powershell
cd "G:\Current Works\ReDoWebs"

# 1. Make sure the shared Postgres container is up
cd "G:\Standalone Services\postgres"
docker compose up -d

# 2. Build and start api + worker (migrate runs once first)
cd "G:\Current Works\ReDoWebs"
docker compose -f standalone/docker-compose.backend.local.yml up --build
```

Verify:

- http://localhost:8123/health → `{"status": "ok"}`
- http://localhost:8123/docs → Swagger UI
- Frontend: `frontend/src/app/core/api-config.ts` already points at `http://localhost:8123`, so `npm start` in `frontend/` works against the containerized backend with no changes.

Useful variations:

```powershell
# Run detached
docker compose -f standalone/docker-compose.backend.local.yml up --build -d

# Tail logs
docker compose -f standalone/docker-compose.backend.local.yml logs -f api worker

# Run a second worker (safe -- claim_next_job() uses SELECT ... FOR UPDATE SKIP LOCKED)
docker compose -f standalone/docker-compose.backend.local.yml up -d --scale worker=2

# Stop (keeps the backend_storage/backend_prompts volumes -- NOT the shared
# Postgres data, which lives in a separate compose project entirely)
docker compose -f standalone/docker-compose.backend.local.yml down

# Re-run migrations only (e.g. after pulling a new migration file)
docker compose -f standalone/docker-compose.backend.local.yml run --rm migrate
```

If `host.docker.internal` doesn't resolve (rare on Docker Desktop, more
common if you ever run this on native Linux Docker Engine instead): the
compose file already sets `extra_hosts: host.docker.internal:host-gateway`
for that case.

## Cloud (generic — any Linux host with Docker + Compose v2)

No specific platform is locked in yet, so `standalone/docker-compose.backend.yml`
is self-contained: it bundles its own Postgres (a named volume, not the
local machine's shared instance — that's Windows/local-only). This runs
as-is on a plain VPS (DigitalOcean/Hetzner/EC2/Lightsail/etc). If you later
adopt a managed Postgres (RDS, Cloud SQL, etc.), delete the `postgres`
service from that file and point `REDOWEBS_DATABASE_URL` at it directly —
`db_pool_size`/`db_max_overflow`/`db_pool_timeout` in `config.py` already
account for multiple worker processes sharing one Postgres instance.

### 1. Prepare the server

```bash
# On the target VM (Ubuntu example)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # re-login after this
```

Copy (or `git clone`) at least `backend/` and `standalone/` onto the
server.

### 2. Create the production secrets file

Create `backend/.env.prod` on the server (never commit it — same rule as
the local `.env`). It uses the same `REDOWEBS_*` variable names documented
in `backend/.env.example`, plus the Postgres credentials this compose file
provisions itself:

```bash
# backend/.env.prod
REDOWEBS_DB_USER=redowebs
REDOWEBS_DB_PASSWORD=<generate a strong password>
REDOWEBS_DB_NAME=redowebs

REDOWEBS_OPENROUTER_API_KEY=<your key>
REDOWEBS_GOOGLE_CLIENT_ID=<your client id>
REDOWEBS_GOOGLE_CLIENT_SECRET=<your client secret>
REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI=https://your-domain.example/api/v1/auth/google/callback
REDOWEBS_FRONTEND_URL=https://your-domain.example
REDOWEBS_JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
```

Remember to also register the real `REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI`
under the OAuth client's "Authorized redirect URIs" in Google Cloud
Console, and update `main.py`'s CORS `allow_origins` (currently hardcoded
to `http://localhost:4200`) to the real deployed frontend origin before
going live — that's an app-code change, not a Docker one.

If your platform has a real secrets manager (AWS Secrets Manager/SSM,
etc.), inject the same `REDOWEBS_*` variables that way instead and skip
`--env-file`/`.env.prod` entirely.

### 3. Build and run

```bash
cd /path/to/ReDoWebs
docker compose -f standalone/docker-compose.backend.yml --env-file backend/.env.prod up -d --build
```

This starts `postgres` → runs `migrate` once → starts `api` (port 8123)
and `worker`, all with `restart: unless-stopped`.

Verify: `curl http://localhost:8123/health` (or through whatever reverse
proxy/load balancer you put in front — see below).

### 4. What's deliberately out of scope here

- **TLS/reverse proxy**: the `api` container only speaks plain HTTP on
  8123. Put Nginx/Caddy/Traefik or your cloud's load balancer in front for
  HTTPS — not included, since it's independent of dockerizing the backend
  itself.
- **Frontend container**: not built here; deploy it however you prefer
  (static hosting, its own container, etc.) and point it at this backend's
  public URL.
- **Rolling/zero-downtime deploys**: this is a single-VM Compose setup, not
  an orchestrator — redeploying (`up -d --build` again) briefly restarts
  `api`/`worker` with the new image.

### 5. Operating it

```bash
# Logs
docker compose -f standalone/docker-compose.backend.yml logs -f api worker

# Scale workers (start conservatively -- see docs/concurrency-scaling-plan.md
# for OpenRouter/DB-pool budget reasoning)
docker compose -f standalone/docker-compose.backend.yml --env-file backend/.env.prod up -d --scale worker=2

# Deploy a new version (after pulling new code)
docker compose -f standalone/docker-compose.backend.yml --env-file backend/.env.prod up -d --build

# Re-run migrations only
docker compose -f standalone/docker-compose.backend.yml --env-file backend/.env.prod run --rm migrate
```

**Never run `down -v`** on a real deployment — that drops the
`postgres_data`, `backend_storage` (crawl snapshots + generated site
output — real user data), and `backend_prompts` (admin-uploaded prompt
templates) volumes.

## Notes shared by both compose files

- `backend_storage` and `backend_prompts` are mounted into **both** `api`
  and `worker` at the same path (`/app/storage_data`, `/app/prompts`) —
  required, not optional: the worker writes generated output and
  admin-uploaded prompt files that the API process later reads/serves
  (see CLAUDE.md's storage and prompt-template bullets).
- `/health` is used as the container healthcheck in both files — wire any
  external uptime monitor/load balancer to the same endpoint.
- No auto-retry is configured anywhere in this stack, matching the
  existing app-level policy (CLAUDE.md) — a failed migration or crashed
  container needs a human to look at logs and restart it, on purpose.
