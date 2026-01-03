"""Celery application configuration for CivicPulse."""

import os

from celery import Celery
from celery.schedules import crontab

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


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
