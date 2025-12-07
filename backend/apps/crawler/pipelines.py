# apps/crawler/pipelines.py

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from apps.sources.models import SiteConfig, CrawlJob
from apps.sources.services import log_crawl_request, finalize_job
from apps.leads.services import upsert_lead

from .base import BaseCrawler, ParseResult
from .http_client import HttpClient, HttpClientConfig, CrawlResponse
from .rate_limit import DomainRateLimiters

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Tracks stats during a crawl pipeline run."""
    pages_crawled: int = 0
    pages_successful: int = 0
    pages_failed: int = 0
    leads_found: int = 0
    leads_created: int = 0
    leads_updated: int = 0
    links_discovered: int = 0
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "pages_crawled": self.pages_crawled,
            "pages_successful": self.pages_successful,
            "pages_failed": self.pages_failed,
            "leads_found": self.leads_found,
            "leads_created": self.leads_created,
            "leads_updated": self.leads_updated,
            "links_discovered": self.links_discovered,
            "error_count": len(self.errors),
        }


class CrawlPipeline:
    """
    Orchestrates the full crawl flow:
    1. Get start URLs from crawler
    2. Fetch each URL (respecting rate limits)
    3. Parse HTML with crawler's parser
    4. Upsert extracted leads
    5. Queue discovered links
    6. Log everything to CrawlLog
    
    Can be run synchronously (for testing) or called from Celery.
    """
    
    def __init__(
        self,
        crawler: BaseCrawler,
        job: CrawlJob,
        http_client: HttpClient | None = None,
        rate_limiters: DomainRateLimiters | None = None,
    ):
        self.crawler = crawler
        self.job = job
        self.http_client = http_client or HttpClient(HttpClientConfig())
        self.rate_limiters = rate_limiters or DomainRateLimiters()
        
        self.stats = PipelineStats()
        self.visited: set[str] = set()
        self.queue: deque[str] = deque()
    
    def run(self) -> PipelineStats:
        """
        Execute the full crawl pipeline.
        Returns stats when complete.
        """
        logger.info(f"Starting crawl for job {self.job.id}: {self.crawler.source_domain}")
        
        # Mark job as running
        self.job.mark_started()
        
        try:
            # Initialize queue with start URLs
            start_urls = self.crawler.get_start_urls()
            for url in start_urls:
                if url not in self.visited:
                    self.queue.append(url)
            
            # Process queue until empty or max pages reached
            while self.queue and self.stats.pages_crawled < self.crawler.max_pages:
                url = self.queue.popleft()
                
                if url in self.visited:
                    continue
                
                self._process_url(url)
                self.visited.add(url)
            
            # Finalize job
            finalize_job(self.job, success=True)
            logger.info(f"Crawl complete for job {self.job.id}: {self.stats.to_dict()}")
            
        except Exception as e:
            error_msg = f"Pipeline error: {str(e)}"
            logger.exception(f"Crawl failed for job {self.job.id}: {e}")
            self.stats.errors.append(error_msg)
            finalize_job(self.job, success=False, error=error_msg)
        
        return self.stats
    
    def _process_url(self, url: str) -> None:
        """Fetch, parse, and process a single URL."""
        logger.debug(f"Processing: {url}")
        
        # Rate limiting
        self.rate_limiters.wait_if_needed(
            url,
            requests_per_minute=self.crawler.requests_per_minute
        )
        
        # Fetch
        response = self._fetch(url)
        self.stats.pages_crawled += 1
        
        if not response.ok:
            self.stats.pages_failed += 1
            self._log_request(url, response, leads_found=0, links_discovered=0)
            return
        
        self.stats.pages_successful += 1
        
        # Parse
        parse_result = self._parse(response)
        
        # Upsert leads
        leads_created, leads_updated = self._upsert_leads(parse_result.leads)
        self.stats.leads_found += len(parse_result.leads)
        self.stats.leads_created += leads_created
        self.stats.leads_updated += leads_updated
        
        # Queue new links
        new_links = self.crawler.filter_links(parse_result.links, self.visited)
        for link in new_links:
            if link not in self.visited and link not in self.queue:
                self.queue.append(link)
        self.stats.links_discovered += len(new_links)
        
        # Log
        self._log_request(
            url, response,
            leads_found=len(parse_result.leads),
            links_discovered=len(new_links)
        )
        
        # Track parse errors
        for error in parse_result.errors:
            self.stats.errors.append(f"{url}: {error}")
    
    def _fetch(self, url: str) -> CrawlResponse:
        """Fetch URL with crawler's custom headers."""
        headers = self.crawler.get_headers()
        return self.http_client.get(url, headers=headers)
    
    def _parse(self, response: CrawlResponse) -> ParseResult:
        """Parse response with crawler's parser."""
        try:
            return self.crawler.parser.parse(response.text, response.url)
        except Exception as e:
            logger.error(f"Parse error for {response.url}: {e}")
            return ParseResult(errors=[str(e)])
    
    def _upsert_leads(self, leads: list) -> tuple[int, int]:
        """Upsert leads and return (created, updated) counts."""
        created = 0
        updated = 0
        
        for parsed_lead in leads:
            try:
                lead, was_created = upsert_lead(**parsed_lead.to_dict())
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                logger.error(f"Error upserting lead {parsed_lead.profile_url}: {e}")
                self.stats.errors.append(f"Upsert error: {e}")
        
        return created, updated
    
    def _log_request(
        self,
        url: str,
        response: CrawlResponse,
        leads_found: int,
        links_discovered: int,
    ) -> None:
        """Log the request to CrawlLog."""
        log_crawl_request(
            crawl_job=self.job,
            url=url,
            http_status=response.status_code,
            content_type=response.content_type,
            duration_ms=response.duration_ms,
            leads_found=leads_found,
            links_discovered=links_discovered,
            error=response.error or "",
        )


def run_crawl_pipeline(
    site_config: SiteConfig,
    job: CrawlJob,
    crawler: BaseCrawler,
) -> PipelineStats:
    """
    Convenience function to run a crawl pipeline.
    Used by Celery tasks.
    """
    pipeline = CrawlPipeline(crawler=crawler, job=job)
    return pipeline.run()