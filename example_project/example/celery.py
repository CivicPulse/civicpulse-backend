"""Celery application configuration for CivicPulse."""

import logging
import os
from logging.handlers import TimedRotatingFileHandler

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")

app = Celery("civicpulse")

# Read config from Django settings with CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat periodic task schedule
app.conf.beat_schedule = {
    "sync-stripe-donations": {
        "task": "civicpulse.tasks.sync_all_active_connections",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
    },
}


@worker_process_init.connect
def configure_worker_logging(sender=None, **kwargs):
    """Configure verbose file logging for Celery workers in development mode.

    Uses TimedRotatingFileHandler with 4-hour rotation to capture all worker
    activity to civicpulse-worker.dev.log. Only activates when DEBUG=True.
    """
    from django.conf import settings

    if not settings.DEBUG:
        return

    # Create verbose formatter matching Django web logging
    formatter = logging.Formatter(
        fmt="[{asctime}] [{levelname}] [{name}:{funcName}:{lineno}] {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create file handler with 4-hour rotation
    handler = TimedRotatingFileHandler(
        filename=settings.BASE_DIR / "civicpulse-worker.dev.log",
        when="H",
        interval=4,
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    # Configure celery and civicpulse loggers
    for logger_name in ("celery", "civicpulse"):
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
