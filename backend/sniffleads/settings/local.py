import os
from .base import *

DEBUG = True

SECRET_KEY = "dev-secret-key-not-for-production"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "web"]

# Works both locally (localhost) and in container (postgres)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "sniffleads",
        "USER": "sniffleads",
        "PASSWORD": "sniffleads",
        "HOST": os.environ.get("DATABASE_HOST", "localhost"),
        "PORT": "5432",
    }
}

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

# Run tasks synchronously in dev for easier debugging
CELERY_TASK_ALWAYS_EAGER = False  # Set True if you want synchronous tasks