# ReDoWebs — Production Deployment (single VPS)

Deploying to one Ubuntu VPS: Postgres + the FastAPI API + N queue workers +
nginx (serving the Angular build and reverse-proxying `/api/` to the API),
all on one box — the same "N `queue_worker.py` processes against one
Postgres" model local dev already uses via `start_workers.ps1`, just run
under systemd instead of PowerShell windows.

This guide deploys over the VPS's **bare IP first** (no domain required to
get running) — §10 covers adding a domain + TLS once you have one, and
lists every place that then needs updating in lockstep.

Every fact below (exact env vars, exact commands, exact files that hardcode
`localhost`) was confirmed by reading the actual repo, not assumed — see
inline notes for what's load-bearing and why.

## 0. Prerequisites

- A VPS: Ubuntu 24.04 LTS, **2 vCPU / 4GB RAM minimum**. 4GB gives headroom
  for Postgres + uvicorn + 2 workers + nginx together — the worker's
  blueprint-review step can burst to 16 concurrent OpenRouter calls via a
  `ThreadPoolExecutor`, and that competes for memory with everything else
  on a smaller box.
- An OpenRouter API key.
- A Google Cloud Console OAuth client (Web application type) — same as
  local dev's `docs/INSTALLATION.md` §2.2, but you'll register a second
  redirect URI for this VPS.
- Root/sudo SSH access to the VPS.

## 1. Provision the VPS

```bash
ufw allow 22
ufw allow 80
ufw allow 443       # reserved for TLS, §10 — harmless to open now
ufw enable
```

Nothing else needs to be public — Postgres stays bound to localhost, the
API is only ever reached through nginx's reverse proxy.

Put `storage_data/` (crawled assets + every generated site) on a disk/mount
sized for growth, not blindly on the OS root volume — it has no
cleanup/retention logic today, so it only grows.

## 2. System packages

```bash
apt update && apt install -y python3.12 python3.12-venv nginx postgresql postgresql-contrib git curl
```

- **No `libpq-dev` needed** — `requirements.txt` pins `psycopg[binary]`,
  which bundles libpq.
- **No browser/Playwright/Selenium install needed** — the crawler is pure
  `httpx` + `beautifulsoup4` + `lxml` (confirmed via a full-tree grep for
  `playwright|selenium|chromium|puppeteer` — zero matches).
- **Node**: install Node 20.19+ or 22.12+ via NodeSource or nvm — not in
  Ubuntu 24.04's default apt repo at the version Angular 20 /
  `@angular/cli ^20.3.3` needs.

## 3. Postgres

There's no compose file or init script in this repo for a fresh production
Postgres — `standalone/docker-compose.yml` is an explicit deprecated
no-op stub (the real dev Postgres is a separate shared container outside
this repo, machine-specific). Create the role/database yourself:

```bash
sudo -u postgres psql -c "CREATE USER redowebs WITH PASSWORD '<generate-a-real-password>';"
sudo -u postgres psql -c "CREATE DATABASE redowebs OWNER redowebs;"
```

Postgres's default `max_connections=100` has plenty of headroom on a
dedicated instance — `db_pool_size=5, db_max_overflow=5` per process, up
to 4 workers + 1 web process, is ≈50 total (see
`docs/concurrency-scaling-plan.md`).

## 4. Backend deploy

```bash
git clone <repo-url> /srv/redowebs
cd /srv/redowebs/backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `/srv/redowebs/backend/.env` (gitignored — real secrets, never
committed):

| Variable | Notes |
|---|---|
| `REDOWEBS_DATABASE_URL` | `postgresql+psycopg://redowebs:<password>@localhost:5432/redowebs` — the dev default points at a different, dev-only DB, so this **must** be set explicitly |
| `REDOWEBS_OPENROUTER_API_KEY` | crawl→blueprint→generate pipeline |
| `REDOWEBS_GOOGLE_CLIENT_ID` / `REDOWEBS_GOOGLE_CLIENT_SECRET` | same Google Cloud Console OAuth client as local dev |
| `REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI` | `http://<vps-ip>/api/v1/auth/google/callback` — must be registered under that OAuth client's "Authorized redirect URIs" |
| `REDOWEBS_FRONTEND_URL` | `http://<vps-ip>` — where the backend redirects the browser after login |
| `REDOWEBS_JWT_SECRET_KEY` | generate fresh: `openssl rand -hex 32` — **do not reuse** the dev `.env`'s value |
| `REDOWEBS_STORAGE_ROOT` | `/var/lib/redowebs/storage_data` — see note below |

`REDOWEBS_STORAGE_ROOT` must be an **absolute path**. The default
(`./storage_data`) resolves relative to the process's working directory,
which is fragile once systemd's `WorkingDirectory=` is in the mix. Create
it and hand it to the service user:

```bash
mkdir -p /var/lib/redowebs/storage_data
chown redowebs:redowebs /var/lib/redowebs/storage_data
```

Run migrations (DB URL is read from `.env` automatically via
`alembic/env.py` — no `alembic.ini` edit needed):

```bash
python -m alembic upgrade head
```

## 5. Required code edits (not just `.env`)

Two URLs are hardcoded in source rather than env-driven — confirmed by
reading the files directly:

- **`backend/app/main.py`** — `CORSMiddleware`'s `allow_origins` is the
  literal list `["http://localhost:4200"]`. Change it to the real frontend
  origin (`["http://<vps-ip>"]` for now). `allow_credentials=True` must
  stay — the OAuth CSRF state cookie depends on it.
- **`backend/app/routers/auth.py`** — the CSRF state cookie is currently
  set `secure=False`. Leave it for this HTTP-only phase; flip to
  `secure=True` in §10 once TLS is on, or the cookie silently stops being
  sent and login breaks with no obvious error.
- **`frontend/src/app/core/api-config.ts`** — `API_BASE_URL` is the
  *only* hardcoded backend URL anywhere in the Angular app (confirmed by a
  full-tree grep — one hit). Since nginx reverse-proxies `/api/` on the
  same origin as the frontend (§8), set this to a relative/empty value
  (same-origin) rather than an absolute `http://<vps-ip>` — that way a
  later domain change only touches nginx config, not a frontend rebuild.

## 6. systemd units

**`/etc/systemd/system/redowebs-api.service`**:

```ini
[Unit]
Description=ReDoWebs API
After=network.target postgresql.service

[Service]
User=redowebs
WorkingDirectory=/srv/redowebs/backend
EnvironmentFile=/srv/redowebs/backend/.env
ExecStart=/srv/redowebs/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8123
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/redowebs-worker@.service`** (templated — mirrors
what `start_workers.ps1` does locally: one `REDOWEBS_WORKER_ID` per
instance, otherwise identical):

```ini
[Unit]
Description=ReDoWebs queue worker %i
After=network.target postgresql.service

[Service]
User=redowebs
WorkingDirectory=/srv/redowebs/backend
EnvironmentFile=/srv/redowebs/backend/.env
Environment=REDOWEBS_WORKER_ID=w%i
ExecStart=/srv/redowebs/backend/venv/bin/python -m app.workers.queue_worker
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Start with **N=2 workers** — matches both `start_workers.ps1`'s default
and `docs/concurrency-scaling-plan.md`'s explicit recommendation to start
conservative:

```bash
systemctl enable --now redowebs-api redowebs-worker@1 redowebs-worker@2
```

## 7. Admin bootstrap

Admin promotion is CLI-only by design — never exposed over HTTP. The
target user **must sign in via Google SSO at least once first**
(`promote_admin.py` looks up an existing `User` row by email and exits 1
if none exists):

```bash
cd /srv/redowebs/backend && source venv/bin/activate
python -m scripts.promote_admin you@example.com
```

To revoke, there's no `demote_admin` script — set `is_admin = false`
directly via `psql`, same as local dev.

## 8. Frontend build + nginx

```bash
cd /srv/redowebs/frontend
npm ci
ng build --configuration production
```

Output lands at `frontend/dist/frontend/browser/` — a pure client-side SPA
build, no SSR.

**`/etc/nginx/sites-available/redowebs`**:

```nginx
server {
    listen 80;
    server_name <vps-ip-or-domain>;

    root /srv/redowebs/frontend/dist/frontend/browser;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;  # SPA client-side routing
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8123/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/redowebs /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

Nothing extra to configure for previews: `/api/v1/preview/{project_id}/...`
is an authenticated dynamic FastAPI route (validates a short-lived JWT,
resolves paths safely under `storage_root`), not a `StaticFiles` mount —
it's already covered by the `/api/` proxy rule above.

## 9. Verification (smoke test)

1. `curl http://127.0.0.1:8123/health` on the VPS, then
   `curl http://<vps-ip>/api/v1/../health` through nginx — both should
   return `{"status": "ok"}`.
2. Open `http://<vps-ip>/` in a browser, sign in via Google, confirm the
   redirect lands back on the SPA logged in. This is the step most likely
   to break from a URL/env mismatch — it exercises
   `REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI`, `REDOWEBS_FRONTEND_URL`, and
   `api-config.ts` all agreeing.
3. Submit a real small site URL; watch it go through
   crawl → blueprint → generate → preview.
4. While a job runs: `SELECT * FROM queued_jobs ORDER BY id DESC LIMIT 5;`
   to confirm rows are being claimed, and
   `SELECT count(*) FROM pg_stat_activity WHERE datname='redowebs';` to
   confirm connections stay well under your `max_connections` budget (the
   same check `docs/concurrency-scaling-plan.md` recommends).
5. Promote yourself admin (§7) and confirm `/admin` loads and shows the
   test project.
6. `journalctl -u redowebs-api -f` / `journalctl -u redowebs-worker@1 -f`
   for live logs — watch specifically for OpenRouter 429s before ever
   raising worker count above 2.

## 10. TLS / domain (once you have a domain)

1. Point an A record at the VPS IP.
2. `apt install certbot python3-certbot-nginx && certbot --nginx -d yourdomain.com`
   — this also rewrites nginx's `listen 80` block to redirect to 443.
3. Update, in lockstep:
   - `.env`: `REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI`, `REDOWEBS_FRONTEND_URL`
   - `backend/app/main.py`: `allow_origins`
   - `frontend/src/app/core/api-config.ts`: `API_BASE_URL` (only if it
     wasn't already relative/same-origin per §5)
   - Google Cloud Console: add the new HTTPS redirect URI
   - `backend/app/routers/auth.py`: flip the CSRF cookie to `secure=True`
4. `systemctl restart redowebs-api` after any `.env`/code change; rebuild
   and redeploy the frontend if `api-config.ts` changed.

## 11. Ongoing: updates and scaling

**Deploying an update:**

```bash
cd /srv/redowebs && git pull
# if requirements.txt changed: pip install -r backend/requirements.txt (venv active)
# if new migrations exist:      python -m alembic upgrade head (venv active, from backend/)
systemctl restart redowebs-api redowebs-worker@1 redowebs-worker@2
# if frontend changed: cd frontend && npm ci && ng build --configuration production
```

**Scaling workers**: only raise past N=2 after confirming (§9.4) no
OpenRouter 429s and no DB pool timeouts under real load. Each worker's
blueprint-review phase alone can burst to 16 concurrent OpenRouter calls,
so total outbound calls scale roughly as `16 × N` during overlapping
phases.

**Backups**: two things need backing up and neither has an automated
mechanism in this repo today — the Postgres DB (`pg_dump`) and
`storage_data/` (plain files, no versioning). A basic cron job (`pg_dump`
+ `tar`/`rsync` of `storage_data` to off-box storage) is a reasonable v1.
