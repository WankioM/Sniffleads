# sniffleads/celery.py

import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sniffleads.settings.local")

app = Celery("sniffleads")

# Load config from Django settings, namespace='CELERY'
# This means all celery-related settings must have CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
# Looks for tasks.py in each app directory
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Test task to verify Celery is working."""
    print(f"Request: {self.request!r}")