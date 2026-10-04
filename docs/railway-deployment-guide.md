# Railway Deployment Guide (CLI-first)

A general guide to deploying apps on [Railway](https://railway.com) with the
Railway CLI. It's based on the ReDoWebs backend deployment (2026-10-04), but
the steps apply to any project. Part 1 covers concepts, Part 2 the commands,
Part 3 common scenarios, Part 4 troubleshooting, and Part 5 the exact
commands run for ReDoWebs.

> Verified against **Railway CLI 5.63.1**. The CLI changes often. If a flag
> here doesn't work, `railway <command> --help` shows the current options.

---

## Part 1 — How Railway works

| Concept | What it is | Why it matters |
|---|---|---|
| **Workspace** | Your account or team. | Projects belong to a workspace. |
| **Project** | A group of services that can reach each other privately. | One app usually means one project (e.g. backend + database). |
| **Environment** | A full copy of the project's services (`production`, `staging`, PR environments). | Variables, settings and volumes are **per environment**. |
| **Service** | One deployable unit: a GitHub repo, a Docker image, or a local upload. | Each service builds and runs **one container** with **one start command**. |
| **Deployment** | One build-and-run of a service. | Has an ID; logs are per deployment. |
| **Volume** | A persistent disk mounted into **one** service. | Everything outside a volume is wiped on every redeploy. |
| **Variables** | Environment variables, per service and per environment. | Can reference other services: `${{Postgres.PGHOST}}`. |
| **Staged changes** | Dashboard edits that are saved but **not applied yet**. | ⚠️ They do nothing until you click **Deploy** on the changes banner at the top of the project canvas. |

### Rules you will run into

1. **One volume per service, and a volume can't be shared between services.**
   If two processes need the same files (e.g. a worker writes files that an
   API serves), they must run in **the same service**, or the files must move
   to object storage (S3/R2). See [Scenario D](#d-two-processes-sharing-files-api--worker-in-one-container).
2. **Services with a volume can't have replicas**, and redeploys have a few
   seconds of downtime (two deployments can't mount the volume at once).
3. **Volumes are mounted as root.** If your Dockerfile switches to a non-root
   user, it can't write to the volume unless you set `RAILWAY_RUN_UID=0`.
4. **Your app must listen on `$PORT`.** Railway sets this variable and routes
   public traffic to it.
5. **Logs on stderr show as errors.** Send normal logs to stdout. JSON logs
   (one object per line with a `level` field) can be filtered by level.
6. **Build context = the service's Root Directory.** In a monorepo, if Root
   Directory is unset, the whole repo is the build context and `COPY` paths
   in a subfolder's Dockerfile fail.

---

## Part 2 — Command reference

### 2.1 Install and log in

```powershell
npm i -g @railway/cli        # or: scoop install railway / brew install railway
railway --version
railway login                # opens a browser; the login is saved for every terminal and tool on this machine
railway login --browserless  # SSH / no-browser machines: prints a link + short code
railway whoami               # check who you're logged in as
```

**Windows:** after a global npm install, a terminal that was already open may
not find `railway`. Open a new terminal, or refresh PATH in the current one:
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

**CI / automation (no browser):** use a token instead of `railway login`.
- *Project token*: project → **Settings → Tokens**. Set it as `RAILWAY_TOKEN`.
  It's limited to one project and environment, which suits CI deploys.
- *Account token*: <https://railway.com/account/tokens>. Set it as
  `RAILWAY_API_TOKEN`. Works across all your projects.

Never commit tokens or paste them into chat or logs.

### 2.2 Find and link a project

`link` remembers which project, environment and service **this local
folder** uses, so later commands don't need `-p/-e/-s`. It only changes a
local setting, nothing on Railway.

```powershell
railway list                 # your projects
railway list --json          # same, plus project/environment/service IDs (useful when two projects have similar names)

railway link                 # interactive picker
railway link --project <project-id> --environment production --service <service-name>   # non-interactive

railway status               # linked project/env/service + deploy status of every service
railway open                 # open the project dashboard in the browser
railway unlink               # forget the link for this folder
```

Tip: pick the project by **what's in it**, not its name. Railway generates
names like `sincere-unity`. `railway list --json` shows each project's
services.

### 2.3 Create projects and services from the CLI

```powershell
railway init --name my-app                        # new empty project
railway add --database postgres                   # managed Postgres (also: mysql, redis, mongo)
railway add --service api --repo owner/repo --branch main     # service from a GitHub repo
railway add --service web --image nginx:latest                # service from a Docker image
railway add --service api --variables "PORT=8000" --variables "LOG_LEVEL=info"
```

**Root Directory, Dockerfile path, start command and pre-deploy command**
are easiest to set in the dashboard (**Service → Settings**). See 2.6.

### 2.4 Deployments and logs

```powershell
railway deployment list                 # recent deployments with IDs and statuses
railway deployment list --json          # full detail, including the build/deploy config that was used

railway logs                            # stream runtime logs of the latest deployment
railway logs <deployment-id>            # a specific deployment
railway logs --build <deployment-id>    # BUILD logs, the first place to look when status = FAILED
railway logs --deployment               # runtime (deploy) logs explicitly
railway logs --http                     # HTTP request logs (status, path, latency)
railway logs -n 200                     # last 200 lines, no streaming
railway logs --since 1h                 # historical window (also --until)
railway logs --filter "@level:error"    # only errors (works when the app logs JSON with a level field)
railway logs --filter "timeout"         # text search
railway logs --http --filter "@httpStatus:500"
railway logs --json                     # machine-readable output
```

**How to read a failed deployment:**
1. `railway deployment list` gives the ID of the `FAILED` one.
2. `railway logs --build <id>`: if the image never built, the error is here
   (missing file, failed `pip install`/`npm install`, etc.).
3. If the build passed, `railway logs <id>` shows runtime crashes (bad start
   command, missing variable, can't reach the database, wrong port).
4. `railway deployment list --json` → `meta.serviceManifest` shows the
   **exact settings that deployment used** (root dir, Dockerfile path, start
   command). This is how you spot settings that were edited but never applied.

### 2.5 Variables

```powershell
railway variables                       # table for the linked service
railway variables --json                # ⚠️ prints RAW secret values
railway variables --set "KEY=value"                    # set one; triggers a redeploy
railway variables --set "A=1" --set "B=2" --skip-deploys   # set several, no redeploy
railway variable set KEY=value          # newer syntax for the same thing
railway variable delete KEY
railway variable edit                   # bulk-edit in $EDITOR with a diff preview
railway run <command>                   # run a LOCAL command with the service's variables injected
```

**Reference variables.** Railway fills these in at deploy time, so keep them
as references rather than copying the values:
```text
DATABASE_URL=postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
OAUTH_REDIRECT_URI=https://${{RAILWAY_PUBLIC_DOMAIN}}/api/v1/auth/google/callback
```
- `${{OtherService.VAR}}` reads another service's variable.
- `${{RAILWAY_PUBLIC_DOMAIN}}` is this service's generated domain, so the
  value follows the domain if it changes.
- In bash, wrap values containing `${{...}}` in **single quotes** so the shell
  doesn't try to expand them.

**Seeing variable names without leaking secrets:**
```powershell
(railway variables --json | ConvertFrom-Json).PSObject.Properties.Name    # PowerShell
railway variables --json | grep -oE '"KEY_NAME": *"[^"]*"'               # bash: one non-secret value
```

**Look for leftover placeholders.** Copying from a guide often leaves
literal `https://<backend-domain>` values behind. Check every URL-type
variable after setup.

### 2.6 Service settings (build/deploy config)

```powershell
railway environment config --json      # ⚠️ dumps ALL services' config INCLUDING secret variable values
```
To read one service's settings without its variables (PowerShell):
```powershell
$cfg = railway environment config --json | Out-String | ConvertFrom-Json
$s = $cfg.services.'<service-id>'
$s.source; $s.build; $s.deploy; $s.volumeMounts
```

The CLI can also change settings with dot-paths:
```powershell
railway environment edit -e production -m "message" `
  --service-config <service> deploy.startCommand "bash start.sh" `
  --service-config <service> deploy.preDeployCommand "alembic upgrade head" `
  --service-config <service> deploy.healthcheckPath "/health" `
  --service-config <service> source.rootDirectory "/backend" `
  --service-config <service> build.dockerfilePath "Dockerfile"
# --stage   stage the changes instead of applying them
```
> ⚠️ **With a `railway login` session this does nothing.** In CLI 5.63.1 it
> returned `{"message":"No changes to apply"}` every time. Calling Railway's
> GraphQL API directly with the same login (`environmentPatchCommit`,
> `serviceInstanceUpdate`) returned **`Not Authorized`**. So the
> browser-login session can read config, add volumes and domains, and set
> variables, but **can't change build/deploy settings**. Options:
> - **Dashboard** (simplest), then **Deploy** on the changes banner.
> - An **account token** (<https://railway.com/account/tokens>, no workspace
>   selected) in `RAILWAY_API_TOKEN` has full rights. Untested here, but it's
>   the documented way to automate settings.
>
> Always check the result with `environment config` or
> `deployment list --json`.

Dashboard locations (**Service → Settings**):

| Setting | Section | Notes |
|---|---|---|
| Root Directory | Source | Monorepo subfolder, e.g. `/backend`. Sets the build context. |
| Branch | Source | Which branch triggers auto-deploys on push. |
| Builder / Dockerfile Path | Build | Path is **relative to Root Directory**, so use `Dockerfile`, not `/backend/Dockerfile`. |
| Custom Start Command | Deploy | Replaces the Dockerfile's `CMD`. The long-running process. |
| Pre-deploy Command | Deploy | Runs once before the new version starts (e.g. migrations). Uses the same image and variables. |
| Healthcheck Path | Deploy | e.g. `/health`. A new deploy only goes live after it returns 200, so a broken build never replaces a working one. |
| Restart Policy | Deploy | `ON_FAILURE` with retries is a sensible default. |
| Cron Schedule | Deploy | Turns the service into a scheduled job (see Scenario H). |

**After editing in the dashboard, click Deploy on the changes banner.** Until
then the old settings stay active.

### 2.7 Volumes

```powershell
railway volume list --json
railway volume --service <service-id> add --mount-path /app/storage_data   # NOTE: --service goes BEFORE 'add'
railway volume attach --volume <volume-name-or-id>
railway volume detach
railway volume files list / --json      # browse files on the volume
railway volume browse /                 # interactive browser
railway volume delete --volume <name> --yes    # ⚠️ permanent data loss
```
- Mount the volume where the app writes, e.g. `/app/storage_data`, and point
  the app's storage setting there (`STORAGE_ROOT=/app/storage_data`).
- A newly added volume may not show in `volume list` until the next
  deployment applies it.
- With a non-root Dockerfile `USER`, set `RAILWAY_RUN_UID=0` (rule 3 in Part 1).

### 2.8 Domains

```powershell
railway domain                          # generate <service>-<env>.up.railway.app
railway domain list
railway domain api.example.com          # custom domain; prints the DNS records to add
railway domain status api.example.com   # DNS/TLS verification status
railway domain delete <domain>
railway domain --port 8000              # when the app doesn't listen on $PORT
```
For a custom domain, add the printed CNAME (and TXT verification record, if
shown) at your DNS provider. Railway issues the HTTPS certificate once DNS
resolves.

### 2.9 Deploy, redeploy, roll back

```powershell
git push origin <branch>               # normal path: GitHub-connected services deploy on push
railway redeploy -y                    # rebuild/re-run the latest deployment (same commit)
railway redeploy --from-source -y      # pull the LATEST commit from the configured branch and deploy it
railway restart -y                     # restart the container without rebuilding
railway up                             # upload the LOCAL folder and deploy it (skips git)
railway up --detach -m "hotfix"        # don't stream logs; attach a message
railway up --ci                        # stream build logs then exit (for CI)
railway down -y                        # remove the most recent deployment (stops the service)
```
- **`railway up` vs `git push`:** `up` deploys whatever is on your disk,
  including uncommitted changes, so production no longer matches any commit.
  Prefer pushing; keep `up` for quick experiments or services that aren't
  connected to GitHub.
- **Rollback:** in the dashboard, **Deployments → (older deployment) → ⋯ →
  Redeploy**. That reuses the old image, which is faster and safer than
  reverting in git while production is down.

### 2.10 Debug inside the running container

```powershell
railway ssh                            # shell inside the running container
railway ssh -- ls -la /app/storage_data   # run one command
railway connect Postgres               # open psql to the managed database
railway connect Postgres --tunnel-only # tunnel for pgAdmin/DBeaver/TablePlus
railway run python -m scripts.some_admin_task   # local script, production variables
```

---

## Part 3 — Scenarios

### A. Monorepo service (backend in a subfolder, built from a Dockerfile)
1. Service → Settings → **Root Directory** `/backend`.
2. **Dockerfile Path** `Dockerfile` (relative to the root directory), or
   empty to auto-detect.
3. All `COPY` lines in the Dockerfile are relative to `/backend`.
4. Set **Watch Paths** (Settings → Build), e.g. `/backend/**`, so pushes
   that only touch other folders don't trigger a backend deploy.

Symptom when Root Directory is wrong:
```
failed to compute cache key: ... "/start.sh": not found
```

### B. Python (FastAPI) + Postgres + migrations
- Add Postgres: `railway add --database postgres`.
- Build `DATABASE_URL` from references (2.5). With SQLAlchemy + psycopg3 use
  the `postgresql+psycopg://` prefix. Railway's own `DATABASE_URL` starts
  with `postgresql://`, which selects the wrong driver.
- **Pre-deploy Command:** `alembic upgrade head`. Don't put it in the start
  command: migrations run, the process exits, and the container restarts
  forever.
- Start: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`. Use
  0.0.0.0, not 127.0.0.1.
- Use the private host (`${{Postgres.PGHOST}}` = `postgres.railway.internal`)
  between services. It's faster and doesn't count as public egress.

### C. Node / static frontend on Railway
- Root Directory `/frontend`, build `npm run build`.
- Start: `npx serve -s <build-output-dir> -l $PORT`. `-s` sends unknown
  paths to index.html so deep links work on reload.
- Generate a domain, then put it in the backend's CORS/frontend-URL variable.

### D. Two processes sharing files (API + worker in one container)
Needed when a worker writes files the API serves, because a volume can't be
shared between services. Use a small supervisor script as the start
command (`bash start.sh`):
```bash
#!/usr/bin/env bash
set -uo pipefail
python -m app.workers.queue_worker &          # process 1
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" &   # process 2
trap 'kill $(jobs -p) 2>/dev/null; wait; exit 0' TERM INT
wait -n                                       # returns when EITHER exits
status=$?; kill $(jobs -p) 2>/dev/null; wait
[ "$status" -eq 0 ] && status=1               # always non-zero so ON_FAILURE restarts the container
exit "$status"
```
Why not just `worker & uvicorn`: if the worker dies, the API keeps running,
the deploy looks healthy, and jobs silently stop. The script stops the whole
container so Railway restarts both processes.

On Windows, make sure the script has **LF** line endings. Add `*.sh text eol=lf`
to `.gitattributes`, or bash fails with `$'\r': command not found`.

### E. Separate worker service (no shared disk needed)
If the API and worker only share the **database** (or files are in S3/R2),
use two services from the same repo and image:
- Service `api`: start command `uvicorn ...`, with a domain.
- Service `worker`: start command `python -m app.workers.queue_worker`, no domain.
- Copy variables or use references (`${{api.SOME_VAR}}`).
This allows replicas and independent restarts. It's the better layout when
it's possible.

### F. Frontend hosted elsewhere (cPanel, Vercel, Netlify…) + backend on Railway
- Bake the Railway backend URL into the frontend build.
- Backend `FRONTEND_URL`/CORS origin = the exact external origin
  (`https://example.com`, no trailing slash).
- OAuth: add the frontend origin as an *Authorized JavaScript origin* and
  the **backend** callback as the redirect URI.
- **cPanel/Apache:** upload the *contents* of the build output folder to
  `public_html/`, plus an `.htaccess` that sends unknown paths to `index.html`:
  ```apache
  RewriteEngine On
  RewriteBase /
  RewriteRule ^index\.html$ - [L]
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule . /index.html [L]
  ```
  Turn on "Show Hidden Files" in File Manager to confirm `.htaccess` uploaded,
  and enable AutoSSL so the site runs on HTTPS.

### G. Staging environment / PR previews
```powershell
railway environment new staging --duplicate production
railway link --environment staging
railway environment list
```
Variables are copied, so **change the secrets and URLs** in staging. Volumes
and databases are separate per environment. PR environments: Project
Settings → Environments → enable PR environments.

### H. Cron / scheduled job
Create a service from the same repo, set its start command to the job
(`python -m scripts.cleanup`) and a **Cron Schedule** (e.g. `0 3 * * *`,
UTC). The process must **exit** when done. Railway skips a run if the
previous one is still going.

### I. Deploy without GitHub (local folder or CI)
```powershell
railway link --project <id> --environment production --service <svc>
railway up --detach
```
CI (GitHub Actions etc.): set `RAILWAY_TOKEN` (project token) as a secret and
run `railway up --ci --service <svc>`.

### J. Config as code (`railway.json` / `railway.toml`)
Instead of dashboard settings, commit a config file:
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": {
    "startCommand": "bash start.sh",
    "preDeployCommand": ["alembic upgrade head"],
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```
Values in the file override the dashboard. In a monorepo, set the file's
location in Service Settings (e.g. `/backend/railway.json`). A config file at
the repo root would apply to **every** service built from the repo.
Root Directory and volumes still have to be set in the dashboard or CLI.

### K. Logging setup that works well on Railway
- All logs to **stdout**. Railway marks every stderr line as an error, which
  includes uvicorn's normal startup lines, since uvicorn logs to stderr by
  default.
- Log **JSON**, one object per line, e.g.
  `{"timestamp":…,"level":"error","logger":…,"message":…,"traceback":…}`.
  Then `railway logs --filter "@level:error"` works, and a multi-line
  traceback stays one entry instead of 30 separate lines.
- Log the **traceback** where exceptions are finally caught. A one-line
  `str(exc)` hides where the failure happened.
- Set `PYTHONUNBUFFERED=1` (Python) so logs appear immediately.
- Make the format configurable (`LOG_FORMAT=json` on Railway, `text`
  locally).

---

## Part 4 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Build: `"/xyz": not found` / `failed to compute cache key` | Wrong Root Directory, so `COPY` paths don't match | Set Root Directory; Dockerfile path relative to it |
| Settings changed in the dashboard but the deploy still uses old ones | Staged changes not applied | Click **Deploy** on the changes banner; check `deployment list --json` → `serviceManifest` |
| Container restarts in a loop, logs show migrations then exit | Migration command used as the **start** command | Move it to **Pre-deploy Command** |
| Deploy "succeeds" but the URL gives 502 | App not on `$PORT`, or bound to `127.0.0.1` | `--host 0.0.0.0 --port $PORT` |
| `Permission denied` writing to the volume | Non-root `USER` in Dockerfile | `RAILWAY_RUN_UID=0` |
| Files disappear after every deploy | Written outside the volume mount path | Point the app's storage path at the mount |
| `$'\r': command not found` in a `.sh` start script | CRLF line endings from Windows | `.gitattributes`: `*.sh text eol=lf`, re-commit |
| Normal INFO logs show red as errors | Logging to stderr | Send logs to stdout (Scenario K) |
| Browser: CORS error on every API call | Backend allowed origin ≠ frontend origin | Set exact origin, no trailing slash |
| OAuth: `redirect_uri_mismatch` | Redirect variable still a placeholder, or not registered with the provider | Fix the variable (`${{RAILWAY_PUBLIC_DOMAIN}}`) and register the URI in the provider console |
| SQLAlchemy picks the wrong driver | Railway URL starts with `postgresql://` | Use `postgresql+psycopg://` (or `+psycopg2`) |
| Git Bash: `Mount path must start with a /` or odd `C:/Program Files/Git/...` values | MSYS rewrites `/paths` into Windows paths | `export MSYS_NO_PATHCONV=1`, or use PowerShell |
| PowerShell: `railway` not found right after install | PATH not refreshed in that terminal | New terminal, or refresh PATH (2.1) |
| `railway environment edit` says "No changes to apply"; API says `Not Authorized` | The CLI login session can't change service settings | Dashboard, or an account token (2.6) |
| Settings edited but the deploy still uses old ones, even after clicking Deploy | Edited a **same-named service in a different project** | Check the project name/ID in the dashboard URL; `railway status` shows the linked one |
| Migration/pre-deploy lines show as errors | Alembic's `alembic.ini` console handler writes to `sys.stderr` | Set `args = (sys.stdout,)` under `[handler_console]` |
| Every submission rejected for low disk | Free-disk threshold larger than the volume | Lower the threshold to fit the plan's volume size |

---

## Part 5 — What was run for ReDoWebs (2026-10-04)

Project `sincere-unity` (Postgres + `ReDoWeb` backend service, branch
`deployable`). A second project, `artistic-luck`, holds a stray `ReDoWeb`
service from an earlier attempt and can be deleted.

```powershell
# 1. Install, check login, identify the project
npm i -g @railway/cli
railway whoami
railway list --json                       # sincere-unity = Postgres + ReDoWeb, so that's the real one

# 2. Link the backend folder (local only)
cd "G:\Current Works\ReDoWebs\backend"
railway link --project c8641988-0b26-4a02-8bdf-907c4e51a67c --environment production --service ReDoWeb
railway status                            # ReDoWeb: Failed, Postgres: Online

# 3. Diagnose the failed deploy
railway deployment list --json            # serviceManifest: rootDirectory null, startCommand "alembic upgrade head", no preDeployCommand, no volume
railway logs --build 66b6a421-3df9-4e7a-90e8-c94a028a8fdf   # "/start.sh": not found, i.e. wrong Root Directory
(railway variables --json | ConvertFrom-Json).PSObject.Properties.Name   # all REDOWEBS_* vars present

# 4. Volume, variables, domain (Git Bash, path conversion off)
export MSYS_NO_PATHCONV=1
railway volume --service c609f79c-02f2-4800-8e6b-b5945d11e053 add --mount-path /app/storage_data
railway variables --set "REDOWEBS_LOG_FORMAT=json" --skip-deploys
railway domain                            # https://redoweb-production.up.railway.app
railway variables --set 'REDOWEBS_GOOGLE_OAUTH_REDIRECT_URI=https://${{RAILWAY_PUBLIC_DOMAIN}}/api/v1/auth/google/callback' --skip-deploys

# 5. Ship the code (structured logging commit)
git push origin deployable
```

```bash
# 6. After the frontend went live on cPanel
railway variables --set "REDOWEBS_FRONTEND_URL=https://www.test.pundraengineeringplc.com" --skip-deploys

# 7. Verify the live deployment
railway deployment list --json             # latest: SUCCESS, root /backend, start "bash start.sh", pre-deploy alembic
curl https://redoweb-production.up.railway.app/health                  # {"status":"ok"}
curl -X OPTIONS https://redoweb-production.up.railway.app/api/v1/auth/me \
  -H "Origin: https://www.test.pundraengineeringplc.com" -H "Access-Control-Request-Method: GET" -D -   # allow-origin = frontend
railway logs -n 3000 | grep -iE "polling|Uvicorn running"              # worker + API both started
railway logs --filter "@level:error"
```

Set in the **dashboard** (the CLI login couldn't change them, see 2.6),
then applied with **Deploy** on the changes banner. The first attempt went
into the same-named `ReDoWeb` service in the `artistic-luck` project:

| Setting | Value |
|---|---|
| Root Directory | `/backend` |
| Dockerfile Path | `Dockerfile` |
| Custom Start Command | `bash start.sh` (API + queue worker, Scenario D) |
| Pre-deploy Command | `alembic upgrade head` |
| Healthcheck Path | `/health` |

Result (2026-10-04): deployment `93778d43` **SUCCESS**. `/health` returns 200,
CORS allows the frontend origin, Google login completes, the worker is
polling, and previews are served from the volume.

| Piece | URL |
|---|---|
| Backend (Railway) | https://redoweb-production.up.railway.app |
| Frontend (cPanel) | https://www.test.pundraengineeringplc.com |

ReDoWebs-specific details (variable list, why API + worker share one
service, prompt-template persistence caveat) are in [RAILWAY.md](RAILWAY.md).

### Post-deploy checklist (any project)
- [ ] `railway status`: service **Online**
- [ ] `railway logs --build <id>` clean; `railway logs` shows the app started
- [ ] `https://<domain>/health` returns 200
- [ ] `railway logs --filter "@level:error"` empty after a smoke test
- [ ] Files written by the app survive a `railway redeploy -y` (volume works)
- [ ] No placeholder values left in variables
- [ ] Frontend → backend calls pass CORS; OAuth login completes
- [ ] Spend cap set (Workspace → Usage)
