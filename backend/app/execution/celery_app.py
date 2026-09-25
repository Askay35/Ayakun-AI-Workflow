from celery import Celery
from pathlib import Path
import sys

from core.config import settings
from core.logging import setup_logging

_argv0 = Path(sys.argv[0]).name if sys.argv else ""
_is_celery = _argv0.startswith("celery") or any(arg in {"worker", "beat"} for arg in sys.argv)
if _is_celery:
    setup_logging("beat" if "beat" in sys.argv else "worker")

celery_app = Celery(
    "ayakun",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["execution.tasks", "execution.billing_tasks"],
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
        },
        "expire-subscriptions": {
            "task": "execution.billing_tasks.expire_subscriptions",
            "schedule": 300.0,
        },
        "remind-expiring-subscriptions": {
            "task": "execution.billing_tasks.remind_expiring_subscriptions",
            "schedule": 3600.0,
        },
    },
)
