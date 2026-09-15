# ReDoWebs — Local Installation & Running

Everything needed to get `standalone/` (Postgres), the FastAPI backend, the
queue worker, and the Angular frontend running on a fresh machine. Written
for Windows (PowerShell), since that's this project's dev environment — Git
Bash equivalents are noted where the command differs.

This machine already runs an unrelated Docker container using the standard
Postgres (5432) port, so `standalone/docker-compose.yml` remaps the host
port to **15432** — that's already baked into `backend/app/config.py`'s
default, nothing to adjust unless your port differs.

Every command block below starts with a `cd` to its **full absolute path** on
this machine, so each block can be run on its own in a fresh terminal without
depending on where a previous block left you.

- Repo root: `G:\Current Works\ReDoWebs`
- Standalone (Docker Compose): `G:\Current Works\ReDoWebs\standalone`
- Backend: `G:\Current Works\ReDoWebs\backend`
- Frontend: `G:\Current Works\ReDoWebs\frontend`

## 0. Prerequisites

- Docker Desktop (for Postgres)
- Python 3.12
- Node.js + npm (for Angular 20 / Tailwind v4)

## 1. Standalone services (Postgres)

```powershell
cd "G:\Current Works\ReDoWebs\standalone"
docker compose up -d
docker compose ps        # should show "healthy"
```

To stop it later: `docker compose down` (add `-v` only if you intentionally
want to wipe the Postgres volume — that deletes all local data).

## 2. Backend (FastAPI + queue worker)

### 2.1 Create the virtualenv and install dependencies

```powershell
cd "G:\Current Works\ReDoWebs\backend"
python -m venv venv
.\venv\Scripts\Activate.ps1        # Git Bash: source venv/Scripts/activate
pip install -r requirements.txt
```

### 2.2 Configure environment variables

```powershell
cd "G:\Current Works\ReDoWebs\backend"
Copy-Item .env.example .env
```

Then fill in `G:\Current Works\ReDoWebs\backend\.env`:

| Variable | Required for | Notes |
|---|---|---|
| `REDOWEBS_OPENROUTER_API_KEY` | crawl→blueprint→generate pipeline | OpenRouter key (used for both the vision call and the generation agent loop) |
| `REDOWEBS_GOOGLE_CLIENT_ID` | Google sign-in | OAuth Client ID from Google Cloud Console (Web application type) |
| `REDOWEBS_GOOGLE_CLIENT_SECRET` | Google sign-in | Client Secret from the same Google Cloud Console OAuth client as the ID above |
| `REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI` | Google sign-in | Defaults to `http://localhost:8123/api/v1/auth/google/callback` — must be registered under that OAuth client's "Authorized redirect URIs" in Google Cloud Console |
| `REDOWEBS_FRONTEND_URL` | Google sign-in | Defaults to `http://localhost:4200` — where the backend redirects the browser after a successful/failed login |
| `REDOWEBS_JWT_SECRET_KEY` | signing our own JWTs | A random secret **you generate** — never reuse the Google Client Secret or any other provider credential here. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |

Auth is Google SSO only right now (no password signup path) and uses a single
JWT with no refresh token — see `docs/PROGRESS.md`'s Milestone 6 notes.

`.env` is gitignored — never commit it. `.env.example` also documents each of
these inline.

### 2.3 Run database migrations

```powershell
cd "G:\Current Works\ReDoWebs\backend"
.\venv\Scripts\Activate.ps1        # Git Bash: source venv/Scripts/activate
python -m alembic upgrade head
```

### 2.4 Start the API server

```powershell
cd "G:\Current Works\ReDoWebs\backend"
.\venv\Scripts\Activate.ps1        # Git Bash: source venv/Scripts/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8123
```

Add `--reload` for auto-restart on code changes during development — but
note: if you ever run it *without* `--reload` (e.g. a plain background
session) and then edit `app/main.py`, you must restart the process manually;
edits won't take effect otherwise.

API docs: http://localhost:8123/docs

### 2.5 Start the queue worker

In a second terminal:

```powershell
cd "G:\Current Works\ReDoWebs\backend"
.\venv\Scripts\Activate.ps1        # Git Bash: source venv/Scripts/activate
python -m app.workers.queue_worker
```

This polls the Postgres-backed `queued_jobs` table and runs the
crawl/blueprint/generate pipeline stages one at a time (see CLAUDE.md) —
no separate broker process to run, unlike the Celery+Redis setup this
replaced.

### 2.6 Run the backend test suite

```powershell
cd "G:\Current Works\ReDoWebs\backend"
.\venv\Scripts\Activate.ps1        # Git Bash: source venv/Scripts/activate
python -m pytest
```

## 3. Frontend (Angular 20 + Tailwind v4)

```powershell
cd "G:\Current Works\ReDoWebs\frontend"
npm install
npm start        # ng serve, http://localhost:4200
```

`G:\Current Works\ReDoWebs\frontend\src\app\core\api-config.ts` hardcodes the
backend URL (`http://localhost:8123`) — no environment files yet, so edit
that file directly if it needs to change. The frontend has no Google config
of its own: Google sign-in is a full-page redirect to the backend, which is
the only side that talks to Google (see the `.env` table above).

To type-check or build without serving:

```powershell
cd "G:\Current Works\ReDoWebs\frontend"
npx tsc -p tsconfig.app.json --noEmit
ng build
```

## 4. Bringing everything up (typical dev session order)

1. `G:\Current Works\ReDoWebs\standalone`: `docker compose up -d`
2. `G:\Current Works\ReDoWebs\backend` (terminal 1): activate venv →
   `python -m uvicorn app.main:app --host 0.0.0.0 --port 8123`
3. `G:\Current Works\ReDoWebs\backend` (terminal 2): activate venv →
   `python -m app.workers.queue_worker`
4. `G:\Current Works\ReDoWebs\frontend` (terminal 3): `npm start`
5. Open http://localhost:4200 — you should land on the welcome/sign-in page.

## 5. Shutting everything down

```powershell
# Ctrl+C in the uvicorn, queue worker, and ng serve terminals, then:
cd "G:\Current Works\ReDoWebs\standalone"
docker compose down       # add -v only if you want to wipe the Postgres volume
```
