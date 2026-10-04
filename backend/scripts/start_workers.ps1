<#
.SYNOPSIS
    Launches multiple app.workers.queue_worker processes for local/dev use.

.DESCRIPTION
    Replaces the single-terminal "python -m app.workers.queue_worker"
    instruction in docs/INSTALLATION.md with N background processes, each
    tagged with a short worker id (REDOWEBS_WORKER_ID) so interleaved stdout
    is distinguishable. Safe to run with any N >= 1 -- claim_next_job()'s
    SELECT ... FOR UPDATE SKIP LOCKED already makes concurrent claiming
    correct; see docs/concurrency-scaling-plan.md for the recommended
    staged rollout (start at 2, confirm no OpenRouter 429s / DB pool
    timeouts, then step up to 3-4).

.PARAMETER Count
    Number of worker processes to start. Default 2.

.EXAMPLE
    .\backend\scripts\start_workers.ps1 -Count 2
#>
param(
    [int]$Count = 2
)

$backendRoot = Split-Path -Parent $PSScriptRoot
$venvActivate = Join-Path $backendRoot "venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
    Write-Error "Virtualenv not found at $venvActivate -- see docs/INSTALLATION.md."
    exit 1
}

for ($i = 1; $i -le $Count; $i++) {
    $workerId = "w$i"
    Write-Host "Starting queue worker $workerId..."
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$backendRoot'; . '$venvActivate'; `$env:REDOWEBS_WORKER_ID = '$workerId'; python -m app.workers.queue_worker"
    )
}

Write-Host "Started $Count queue worker process(es) in separate windows."
