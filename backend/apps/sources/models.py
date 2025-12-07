# apps/sources/models.py

from django.db import models
from django.utils import timezone

from apps.common.models import TimestampedModel
from apps.common.enums import SourceType, CrawlJobStatus


class SiteConfig(TimestampedModel):
    """
    Configuration for a crawl source.
    Defines what to crawl and how.
    """
    domain = models.CharField(max_length=255, db_index=True)
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.CUSTOM,
        db_index=True,
    )
    name = models.CharField(max_length=255, help_text="Human-readable name")
    enabled = models.BooleanField(default=True, db_index=True)
    
    # Crawl configuration
    start_urls = models.JSONField(
        default=list,
        help_text="List of seed URLs to start crawling from",
    )
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Source-specific filters (tags, subreddits, etc.)",
    )
    
    # Rate limiting
    requests_per_minute = models.PositiveIntegerField(
        default=10,
        help_text="Max requests per minute for this source",
    )
    
    # Scheduling
    crawl_interval_hours = models.PositiveIntegerField(
        default=24,
        help_text="Hours between automated crawls",
    )
    last_crawl_at = models.DateTimeField(null=True, blank=True)
    
    # Auth/credentials reference (actual secrets in env/vault)
    credentials_key = models.CharField(
        max_length=100,
        blank=True,
        help_text="Key to look up credentials in secrets store",
    )
    
    # Scraper behavior
    max_pages = models.PositiveIntegerField(
        default=100,
        help_text="Max pages to crawl per job",
    )
    follow_links = models.BooleanField(
        default=True,
        help_text="Whether to follow discovered links",
    )
    use_browser = models.BooleanField(
        default=False,
        help_text="Use headless browser instead of HTTP client",
    )

    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configurations"
        ordering = ["domain", "name"]
        indexes = [
            models.Index(fields=["enabled", "source_type"]),
            models.Index(fields=["last_crawl_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.domain})"

    def is_due_for_crawl(self) -> bool:
        if not self.enabled:
            return False
        if self.last_crawl_at is None:
            return True
        delta = timezone.now() - self.last_crawl_at
        return delta.total_seconds() >= self.crawl_interval_hours * 3600


class CrawlJob(TimestampedModel):
    """
    A single crawl execution against a SiteConfig.
    Tracks status, timing, and aggregate stats.
    """
    site_config = models.ForeignKey(
        SiteConfig,
        on_delete=models.CASCADE,
        related_name="crawl_jobs",
    )
    status = models.CharField(
        max_length=20,
        choices=CrawlJobStatus.choices,
        default=CrawlJobStatus.PENDING,
        db_index=True,
    )
    
    # Timing
    scheduled_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the job was scheduled to run",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    # Execution context
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    triggered_by = models.CharField(
        max_length=50,
        default="manual",
        help_text="scheduler, manual, api, etc.",
    )
    
    # Results
    stats = models.JSONField(
        default=dict,
        blank=True,
        help_text="Aggregate stats: pages_crawled, leads_found, errors, etc.",
    )
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = "Crawl Job"
        verbose_name_plural = "Crawl Jobs"
        ordering = ["-scheduled_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"]),
            models.Index(fields=["site_config", "status"]),
            models.Index(fields=["-started_at"]),
            models.Index(fields=["-finished_at"]),
        ]

    def __str__(self):
        return f"Job {self.id} - {self.site_config.name} ({self.status})"

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def mark_started(self):
        self.status = CrawlJobStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self, stats: dict | None = None):
        self.status = CrawlJobStatus.COMPLETED
        self.finished_at = timezone.now()
        if stats:
            self.stats = stats
        self.save(update_fields=["status", "finished_at", "stats", "updated_at"])
        # Update parent config
        self.site_config.last_crawl_at = self.finished_at
        self.site_config.save(update_fields=["last_crawl_at", "updated_at"])

    def mark_failed(self, error: str, stats: dict | None = None):
        self.status = CrawlJobStatus.FAILED
        self.finished_at = timezone.now()
        self.error_message = error
        if stats:
            self.stats = stats
        self.save(update_fields=["status", "finished_at", "error_message", "stats", "updated_at"])


class CrawlLog(models.Model):
    """
    Per-URL log entry for a crawl job.
    Tracks individual page fetches for debugging and analytics.
    """
    crawl_job = models.ForeignKey(
        CrawlJob,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    url = models.URLField(max_length=2048)
    
    # Response info
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    
    # Timing
    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Request duration in milliseconds",
    )
    
    # Results
    leads_found = models.PositiveIntegerField(default=0)
    links_discovered = models.PositiveIntegerField(default=0)
    
    # Errors
    error = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Crawl Log"
        verbose_name_plural = "Crawl Logs"
        ordering = ["-fetched_at"]
        indexes = [
            models.Index(fields=["crawl_job", "http_status"]),
            models.Index(fields=["crawl_job", "-fetched_at"]),
            models.Index(fields=["http_status"]),
        ]

    def __str__(self):
        status = self.http_status or "ERR"
        return f"[{status}] {self.url[:80]}"

    @property
    def is_success(self) -> bool:
        return self.http_status is not None and 200 <= self.http_status < 400

    @property
    def is_error(self) -> bool:
        return bool(self.error) or (self.http_status and self.http_status >= 400)