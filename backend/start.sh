#!/usr/bin/env bash
# Runs the API and the queue worker in ONE container -- for platforms
# (Railway) where a disk volume can only attach to a single service, so the
# worker (writes generated output) and the API (serves it via /preview) must
# share a filesystem by sharing a container. Docker Compose setups don't use
# this: they run api/worker as separate services sharing named volumes (see
# docs/DOCKER.md), and the Dockerfile's default CMD stays uvicorn-only.
#
# If either process exits, the other is stopped and the container exits
# non-zero, so the platform's restart policy restarts both together instead
# of leaving a live API with a silently dead worker.
set -uo pipefail

python -m app.workers.queue_worker &
worker_pid=$!
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8123}" &
api_pid=$!

stop_children() {
  kill "$worker_pid" "$api_pid" 2>/dev/null
  wait
}
trap 'stop_children; exit 0' TERM INT

wait -n
status=$?
echo "start.sh: a process exited (status ${status}); stopping container" >&2
stop_children
# Exit non-zero even if the dead process exited 0 -- either one stopping is
# unexpected here, and on-failure restart policies only fire on non-zero.
if [ "$status" -eq 0 ]; then status=1; fi
exit "$status"
