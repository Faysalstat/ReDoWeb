from celery import Celery

from ..config import get_settings

_settings = get_settings()

celery_app = Celery(
    "redowebs",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=[
        "app.workers.tasks_crawl",
        "app.workers.tasks_blueprint",
        "app.workers.tasks_generate",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
