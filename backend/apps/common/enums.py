# apps/common/enums.py

from django.db import models


class SourceType(models.TextChoices):
    """Types of lead sources we can crawl."""
    LINKEDIN = "linkedin", "LinkedIn"
    REDDIT = "reddit", "Reddit"
    MEDIUM = "medium", "Medium"
    TWITTER = "twitter", "Twitter"
    CUSTOM = "custom", "Custom"


class CrawlJobStatus(models.TextChoices):
    """Status states for crawl jobs."""
    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"