from celery import Celery

from core.config import settings
from core.logging import setup_logging
import sys

setup_logging("beat" if "beat" in sys.argv else "worker")

celery_app = Celery(
    "ayakun",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["execution.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_soft_time_limit=840,
    task_time_limit=900,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,
    beat_schedule={
        "poll-scheduled-workflows": {
            "task": "execution.tasks.poll_scheduled_workflows",
            "schedule": 60.0,
        }
    },
)
