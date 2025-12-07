# apps/sources/selectors.py

from django.db.models import QuerySet, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .models import SiteConfig, CrawlJob, CrawlLog, CrawlJobStatus, SourceType


# === SiteConfig Selectors ===

def get_site_config_by_id(config_id: int) -> SiteConfig | None:
    return SiteConfig.objects.filter(id=config_id).first()


def get_site_config_by_domain(domain: str) -> SiteConfig | None:
    return SiteConfig.objects.filter(domain=domain).first()


def get_enabled_configs() -> QuerySet[SiteConfig]:
    return SiteConfig.objects.filter(enabled=True)


def get_configs_by_source_type(source_type: str) -> QuerySet[SiteConfig]:
    return SiteConfig.objects.filter(source_type=source_type, enabled=True)


def get_all_configs() -> QuerySet[SiteConfig]:
    return SiteConfig.objects.all().order_by("domain", "name")


# === CrawlJob Selectors ===

def get_job_by_id(job_id: int) -> CrawlJob | None:
    return CrawlJob.objects.select_related("site_config").filter(id=job_id).first()


def get_jobs_by_status(status: str) -> QuerySet[CrawlJob]:
    return CrawlJob.objects.filter(status=status).select_related("site_config")


def get_jobs_for_config(config: SiteConfig) -> QuerySet[CrawlJob]:
    return config.crawl_jobs.all().order_by("-scheduled_at")


def get_latest_job_for_config(config: SiteConfig) -> CrawlJob | None:
    return config.crawl_jobs.order_by("-scheduled_at").first()


def get_running_jobs() -> QuerySet[CrawlJob]:
    return CrawlJob.objects.filter(status=CrawlJobStatus.RUNNING).select_related("site_config")


def get_pending_jobs() -> QuerySet[CrawlJob]:
    return CrawlJob.objects.filter(
        status__in=[CrawlJobStatus.PENDING, CrawlJobStatus.QUEUED]
    ).select_related("site_config").order_by("scheduled_at")


def get_recent_jobs(hours: int = 24) -> QuerySet[CrawlJob]:
    since = timezone.now() - timedelta(hours=hours)
    return CrawlJob.objects.filter(
        scheduled_at__gte=since
    ).select_related("site_config").order_by("-scheduled_at")


def get_failed_jobs(hours: int = 24) -> QuerySet[CrawlJob]:
    since = timezone.now() - timedelta(hours=hours)
    return CrawlJob.objects.filter(
        status=CrawlJobStatus.FAILED,
        finished_at__gte=since,
    ).select_related("site_config").order_by("-finished_at")


# === CrawlLog Selectors ===

def get_logs_for_job(job: CrawlJob) -> QuerySet[CrawlLog]:
    return job.logs.all().order_by("-fetched_at")


def get_error_logs_for_job(job: CrawlJob) -> QuerySet[CrawlLog]:
    return job.logs.filter(
        Q(http_status__gte=400) | ~Q(error="")
    ).order_by("-fetched_at")


def get_successful_logs_for_job(job: CrawlJob) -> QuerySet[CrawlLog]:
    return job.logs.filter(
        http_status__gte=200,
        http_status__lt=400,
        error="",
    ).order_by("-fetched_at")


# === Aggregate Stats ===

def get_crawl_stats_summary() -> dict:
    """Get high-level crawl statistics."""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    
    jobs_24h = CrawlJob.objects.filter(scheduled_at__gte=last_24h)
    jobs_7d = CrawlJob.objects.filter(scheduled_at__gte=last_7d)
    
    return {
        "active_configs": SiteConfig.objects.filter(enabled=True).count(),
        "total_configs": SiteConfig.objects.count(),
        "running_jobs": CrawlJob.objects.filter(status=CrawlJobStatus.RUNNING).count(),
        "pending_jobs": CrawlJob.objects.filter(
            status__in=[CrawlJobStatus.PENDING, CrawlJobStatus.QUEUED]
        ).count(),
        "jobs_24h": {
            "total": jobs_24h.count(),
            "completed": jobs_24h.filter(status=CrawlJobStatus.COMPLETED).count(),
            "failed": jobs_24h.filter(status=CrawlJobStatus.FAILED).count(),
        },
        "jobs_7d": {
            "total": jobs_7d.count(),
            "completed": jobs_7d.filter(status=CrawlJobStatus.COMPLETED).count(),
            "failed": jobs_7d.filter(status=CrawlJobStatus.FAILED).count(),
        },
    }


def get_config_performance(config: SiteConfig, days: int = 7) -> dict:
    """Get performance metrics for a specific config."""
    since = timezone.now() - timedelta(days=days)
    jobs = config.crawl_jobs.filter(scheduled_at__gte=since)
    
    completed = jobs.filter(status=CrawlJobStatus.COMPLETED)
    failed = jobs.filter(status=CrawlJobStatus.FAILED)
    
    # Aggregate from completed job stats
    total_leads = 0
    total_pages = 0
    for job in completed:
        stats = job.stats or {}
        total_leads += stats.get("leads_found", 0)
        total_pages += stats.get("pages_crawled", 0)
    
    return {
        "jobs_total": jobs.count(),
        "jobs_completed": completed.count(),
        "jobs_failed": failed.count(),
        "success_rate": (
            round(completed.count() / jobs.count() * 100, 1)
            if jobs.count() > 0 else 0
        ),
        "total_leads_found": total_leads,
        "total_pages_crawled": total_pages,
    }