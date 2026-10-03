# Single image for both the FastAPI API process and the queue worker
# process (app/workers/queue_worker.py) -- which one runs is decided by the
# `command:` a compose file (or cloud platform) passes in, not by this file.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY prompts ./prompts
# Opt-in API+worker-in-one-container entrypoint for Railway (see the script's
# header) -- not the default CMD, which the compose files rely on.
COPY start.sh .

# storage_root (config.py) and prompts/ are both written to at runtime
# (generated site output, and admin-uploaded prompt templates respectively)
# -- both are volume-mounted by the compose files, but the mountpoint/dir
# has to exist and be owned by the non-root user first.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/storage_data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8123

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"]
