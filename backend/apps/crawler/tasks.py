# apps/crawler/tasks.py

import logging
from celery import shared_task

from apps.sources.models import CrawlJob, SiteConfig
from apps.sources.services import create_crawl_job, queue_crawl_job
from apps.sources.selectors import get_job_by_id, get_site_config_by_id
from apps.common.enums import CrawlJobStatus

from .base import CrawlerRegistry
from .pipelines import CrawlPipeline

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def run_crawl_job(self, job_id: int) -> dict:
    """
    Execute a crawl job.
    
    This is the main entry point for running crawls asynchronously.
    Called by the scheduler or triggered manually.
    
    Args:
        job_id: ID of the CrawlJob to execute
        
    Returns:
        dict with job stats
    """
    job = get_job_by_id(job_id)
    
    if not job:
        logger.error(f"CrawlJob {job_id} not found")
        return {"error": f"Job {job_id} not found"}
    
    if job.status not in (CrawlJobStatus.PENDING, CrawlJobStatus.QUEUED):
        logger.warning(f"Job {job_id} has status {job.status}, skipping")
        return {"error": f"Job already {job.status}"}
    
    site_config = job.site_config
    
    if not site_config.enabled:
        logger.warning(f"SiteConfig {site_config.id} is disabled, skipping job {job_id}")
        job.mark_failed("Site config is disabled")
        return {"error": "Site config disabled"}
    
    # Get the crawler for this source type
    crawler = CrawlerRegistry.get_crawler(site_config.source_type, site_config)
    
    if not crawler:
        error = f"No crawler registered for source type: {site_config.source_type}"
        logger.error(error)
        job.mark_failed(error)
        return {"error": error}
    
    # Run the pipeline
    logger.info(f"Starting crawl job {job_id} for {site_config.name}")
    
    pipeline = CrawlPipeline(crawler=crawler, job=job)
    stats = pipeline.run()
    
    logger.info(f"Crawl job {job_id} complete: {stats.to_dict()}")
    return stats.to_dict()


@shared_task(bind=True, max_retries=2)
def crawl_single_url(
    self,
    url: str,
    site_config_id: int,
    job_id: int | None = None,
) -> dict:
    """
    Crawl a single URL.
    
    Useful for:
    - Retrying specific failed URLs
    - Testing parsers
    - Ad-hoc crawling
    
    Args:
        url: URL to crawl
        site_config_id: SiteConfig to use for crawler settings
        job_id: Optional CrawlJob to log results to
    """
    from .http_client import HttpClient, HttpClientConfig
    from .rate_limit import DomainRateLimiters
    from apps.sources.services import log_crawl_request
    from apps.leads.services import upsert_lead
    
    site_config = get_site_config_by_id(site_config_id)
    if not site_config:
        return {"error": f"SiteConfig {site_config_id} not found"}
    
    crawler = CrawlerRegistry.get_crawler(site_config.source_type, site_config)
    if not crawler:
        return {"error": f"No crawler for {site_config.source_type}"}
    
    # Rate limit
    rate_limiters = DomainRateLimiters()
    rate_limiters.wait_if_needed(url, site_config.requests_per_minute)
    
    # Fetch
    client = HttpClient(HttpClientConfig())
    response = client.get(url, headers=crawler.get_headers())
    
    result = {
        "url": url,
        "status_code": response.status_code,
        "duration_ms": response.duration_ms,
        "error": response.error,
        "leads_found": 0,
    }
    
    if not response.ok:
        return result
    
    # Parse
    parse_result = crawler.parser.parse(response.text, response.url)
    result["leads_found"] = len(parse_result.leads)
    result["links_discovered"] = len(parse_result.links)
    
    # Upsert leads
    for lead in parse_result.leads:
        try:
            upsert_lead(**lead.to_dict())
        except Exception as e:
            logger.error(f"Failed to upsert lead: {e}")
    
    # Log if job provided
    if job_id:
        job = get_job_by_id(job_id)
        if job:
            log_crawl_request(
                crawl_job=job,
                url=url,
                http_status=response.status_code,
                content_type=response.content_type,
                duration_ms=response.duration_ms,
                leads_found=len(parse_result.leads),
                links_discovered=len(parse_result.links),
                error=response.error or "",
            )
    
    return result


@shared_task
def trigger_crawl_for_config(site_config_id: int, triggered_by: str = "manual") -> dict:
    """
    Create and queue a crawl job for a site config.
    
    Convenience task that creates the job and immediately queues it.
    
    Args:
        site_config_id: SiteConfig to crawl
        triggered_by: Who triggered this (manual, scheduler, api)
        
    Returns:
        dict with job_id and task_id
    """
    site_config = get_site_config_by_id(site_config_id)
    if not site_config:
        return {"error": f"SiteConfig {site_config_id} not found"}
    
    if not site_config.enabled:
        return {"error": "SiteConfig is disabled"}
    
    # Create job
    job = create_crawl_job(site_config, triggered_by=triggered_by)
    
    # Queue async execution
    task = run_crawl_job.delay(job.id)
    
    # Update job with task ID
    queue_crawl_job(job, celery_task_id=task.id)
    
    logger.info(f"Queued crawl job {job.id} (task {task.id}) for {site_config.name}")
    
    return {
        "job_id": job.id,
        "task_id": task.id,
        "site_config": site_config.name,
    }