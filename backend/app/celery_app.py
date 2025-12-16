import os
from celery import Celery
from .config import get_settings

settings = get_settings()

celery = Celery(
    "codex",
    broker=settings.broker_url,
    backend=settings.redis_url,
)
celery.conf.beat_schedule = {
    "check-calendar": {
        "task": "tasks.enqueue_due_plans",
        "schedule": 3600,
    }
}


@celery.task(name="tasks.enqueue_due_plans")
def enqueue_due_plans():
    # placeholder: in real app would enqueue jobs for near-term slots
    return "ok"
