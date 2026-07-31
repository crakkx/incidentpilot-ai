import os
from celery import Celery

redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url,
    include=["app.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

from celery.signals import worker_process_init, setup_logging
from app.core.logging import configure_logging

@setup_logging.connect
def config_loggers(*args, **kwargs):
    configure_logging()

@worker_process_init.connect
def init_worker(**kwargs):
    try:
        import mlflow
        import os
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("IncidentPilot-RCA")
    except ImportError:
        pass
