# apps/sources/tasks.py

import logging
from celery import shared_task

from .models import SiteConfig
from .services import get_configs_due_for_crawl
from apps.crawler.tasks import trigger_crawl_for_config

logger = logging.getLogger(__name__)


@shared_task
def schedule_crawl_jobs() -> dict:
    """
    Check all site configs and trigger crawls for those that are due.
    
    This task runs periodically via Celery Beat (e.g., every 15 minutes).
    It checks each enabled SiteConfig's last_crawl_at against its
    crawl_interval_hours to determine if a new crawl should start.
    
    Returns:
        dict with counts of triggered jobs
    """
    configs_due = get_configs_due_for_crawl()
    
    triggered = 0
    skipped = 0
    errors = []
    
    for config in configs_due:
        try:
            result = trigger_crawl_for_config.delay(
                site_config_id=config.id,
                triggered_by="scheduler",
            )
            logger.info(f"Scheduled crawl for {config.name} (task: {result.id})")
            triggered += 1
            
        except Exception as e:
            error_msg = f"Failed to schedule {config.name}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            skipped += 1
    
    summary = {
        "configs_checked": len(configs_due),
        "jobs_triggered": triggered,
        "jobs_skipped": skipped,
        "errors": errors,
    }
    
    logger.info(f"Scheduler run complete: {summary}")
    return summary


@shared_task
def cleanup_old_crawl_logs(days: int = 30) -> dict:
    """
    Delete crawl logs older than specified days.
    
    Keeps the database from growing unbounded.
    Run weekly or monthly via Celery Beat.
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import CrawlLog
    
    cutoff = timezone.now() - timedelta(days=days)
    
    # Get count before delete
    old_logs = CrawlLog.objects.filter(fetched_at__lt=cutoff)
    count = old_logs.count()
    
    # Delete in batches to avoid long locks
    deleted = 0
    batch_size = 1000
    
    while True:
        batch = list(old_logs[:batch_size].values_list("id", flat=True))
        if not batch:
            break
        CrawlLog.objects.filter(id__in=batch).delete()
        deleted += len(batch)
        logger.info(f"Deleted {deleted}/{count} old crawl logs")
    
    return {
        "logs_deleted": deleted,
        "cutoff_date": cutoff.isoformat(),
    }


@shared_task
def health_check() -> dict:
    """
    Simple health check task.
    
    Used to verify Celery workers are running.
    Can be triggered manually or via Beat for monitoring.
    """
    from django.utils import timezone
    from .selectors import get_crawl_stats_summary
    
    return {
        "status": "healthy",
        "timestamp": timezone.now().isoformat(),
        "stats": get_crawl_stats_summary(),
    }