# apps/sources/services.py

from django.db import transaction
from django.utils import timezone

from .models import SiteConfig, CrawlJob, CrawlLog, CrawlJobStatus, SourceType


def create_site_config(
    domain: str,
    name: str,
    source_type: str = SourceType.CUSTOM,
    start_urls: list[str] | None = None,
    filters: dict | None = None,
    **kwargs,
) -> SiteConfig:
    """Create a new site configuration."""
    return SiteConfig.objects.create(
        domain=domain,
        name=name,
        source_type=source_type,
        start_urls=start_urls or [],
        filters=filters or {},
        **kwargs,
    )


def update_site_config(config: SiteConfig, **kwargs) -> SiteConfig:
    """Update an existing site configuration."""
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.save()
    return config


def create_crawl_job(
    site_config: SiteConfig,
    triggered_by: str = "manual",
    scheduled_at: timezone.datetime | None = None,
) -> CrawlJob:
    """Create a new crawl job for a site config."""
    return CrawlJob.objects.create(
        site_config=site_config,
        triggered_by=triggered_by,
        scheduled_at=scheduled_at or timezone.now(),
        status=CrawlJobStatus.PENDING,
    )


def queue_crawl_job(job: CrawlJob, celery_task_id: str) -> CrawlJob:
    """Mark a job as queued with its Celery task ID."""
    job.status = CrawlJobStatus.QUEUED
    job.celery_task_id = celery_task_id
    job.save(update_fields=["status", "celery_task_id", "updated_at"])
    return job


def cancel_crawl_job(job: CrawlJob) -> CrawlJob:
    """Cancel a pending or queued job."""
    if job.status in (CrawlJobStatus.PENDING, CrawlJobStatus.QUEUED):
        job.status = CrawlJobStatus.CANCELLED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at", "updated_at"])
    return job


def log_crawl_request(
    crawl_job: CrawlJob,
    url: str,
    http_status: int | None = None,
    content_type: str = "",
    duration_ms: int | None = None,
    leads_found: int = 0,
    links_discovered: int = 0,
    error: str = "",
    retry_count: int = 0,
) -> CrawlLog:
    """Log a single URL fetch within a crawl job."""
    return CrawlLog.objects.create(
        crawl_job=crawl_job,
        url=url,
        http_status=http_status,
        content_type=content_type,
        duration_ms=duration_ms,
        leads_found=leads_found,
        links_discovered=links_discovered,
        error=error,
        retry_count=retry_count,
    )


def compute_job_stats(job: CrawlJob) -> dict:
    """Compute aggregate stats from crawl logs."""
    logs = job.logs.all()
    
    total = logs.count()
    successful = logs.filter(http_status__gte=200, http_status__lt=400).count()
    failed = logs.filter(http_status__gte=400).count()
    errors = logs.exclude(error="").count()
    
    from django.db.models import Sum, Avg
    aggregates = logs.aggregate(
        total_leads=Sum("leads_found"),
        total_links=Sum("links_discovered"),
        avg_duration=Avg("duration_ms"),
    )
    
    return {
        "pages_crawled": total,
        "pages_successful": successful,
        "pages_failed": failed,
        "pages_with_errors": errors,
        "leads_found": aggregates["total_leads"] or 0,
        "links_discovered": aggregates["total_links"] or 0,
        "avg_duration_ms": round(aggregates["avg_duration"] or 0, 2),
    }


@transaction.atomic
def finalize_job(job: CrawlJob, success: bool = True, error: str = "") -> CrawlJob:
    """Finalize a job, computing stats and updating status."""
    stats = compute_job_stats(job)
    
    if success:
        job.mark_completed(stats=stats)
    else:
        job.mark_failed(error=error, stats=stats)
    
    return job


def get_configs_due_for_crawl() -> list[SiteConfig]:
    """Get all enabled configs that are due for their scheduled crawl."""
    configs = SiteConfig.objects.filter(enabled=True)
    return [c for c in configs if c.is_due_for_crawl()]