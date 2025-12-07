# apps/crawler/http_client.py

import httpx
import random
import time
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@dataclass
class CrawlResponse:
    """Standardized response from HTTP client."""
    url: str
    status_code: int | None
    content: bytes
    text: str
    headers: dict[str, str]
    duration_ms: int
    error: str | None = None
    
    @property
    def ok(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 400
    
    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip()


@dataclass 
class HttpClientConfig:
    """Configuration for the HTTP client."""
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0  # Exponential backoff multiplier
    rotate_user_agent: bool = True
    proxies: list[str] | None = None
    verify_ssl: bool = True
    follow_redirects: bool = True
    max_redirects: int = 10
    
    # Default headers
    default_headers: dict[str, str] | None = None


class HttpClient:
    """
    HTTP client wrapper with retries, user-agent rotation, and proxy support.
    Designed for web scraping with polite defaults.
    """
    
    def __init__(self, config: HttpClientConfig | None = None):
        self.config = config or HttpClientConfig()
        self._proxy_index = 0
    
    def _get_headers(self, extra_headers: dict | None = None) -> dict[str, str]:
        """Build request headers with optional user-agent rotation."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        
        if self.config.rotate_user_agent:
            headers["User-Agent"] = random.choice(USER_AGENTS)
        else:
            headers["User-Agent"] = USER_AGENTS[0]
        
        if self.config.default_headers:
            headers.update(self.config.default_headers)
        
        if extra_headers:
            headers.update(extra_headers)
        
        return headers
    
    def _get_proxy(self) -> str | None:
        """Get next proxy from rotation list."""
        if not self.config.proxies:
            return None
        proxy = self.config.proxies[self._proxy_index % len(self.config.proxies)]
        self._proxy_index += 1
        return proxy
    
    def _should_retry(self, status_code: int | None, attempt: int) -> bool:
        """Determine if request should be retried."""
        if attempt >= self.config.max_retries:
            return False
        if status_code is None:  # Connection error
            return True
        # Retry on server errors and rate limits
        return status_code >= 500 or status_code == 429
    
    def fetch(
        self,
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        params: dict | None = None,
        data: dict | None = None,
        json: dict | None = None,
    ) -> CrawlResponse:
        """
        Fetch a URL with retries and error handling.
        Returns CrawlResponse with standardized fields.
        """
        attempt = 0
        last_error = None
        
        while attempt <= self.config.max_retries:
            start_time = time.time()
            
            try:
                proxy = self._get_proxy()
                
                with httpx.Client(
                    timeout=self.config.timeout,
                    follow_redirects=self.config.follow_redirects,
                    max_redirects=self.config.max_redirects,
                    verify=self.config.verify_ssl,
                    proxy=proxy,
                ) as client:
                    response = client.request(
                        method=method,
                        url=url,
                        headers=self._get_headers(headers),
                        params=params,
                        data=data,
                        json=json,
                    )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Check if we should retry
                if self._should_retry(response.status_code, attempt):
                    attempt += 1
                    delay = self.config.retry_delay * (self.config.retry_backoff ** (attempt - 1))
                    logger.warning(
                        f"Retry {attempt}/{self.config.max_retries} for {url} "
                        f"(status={response.status_code}), waiting {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                
                return CrawlResponse(
                    url=str(response.url),
                    status_code=response.status_code,
                    content=response.content,
                    text=response.text,
                    headers=dict(response.headers),
                    duration_ms=duration_ms,
                )
                
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                logger.warning(f"Timeout fetching {url}: {e}")
                
            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Connection error for {url}: {e}")
                
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP error: {e}"
                logger.warning(f"HTTP error for {url}: {e}")
                
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.error(f"Unexpected error fetching {url}: {e}")
            
            # Retry logic for exceptions
            attempt += 1
            if attempt <= self.config.max_retries:
                delay = self.config.retry_delay * (self.config.retry_backoff ** (attempt - 1))
                logger.info(f"Retrying {url} in {delay:.1f}s (attempt {attempt})")
                time.sleep(delay)
        
        # All retries exhausted
        duration_ms = int((time.time() - start_time) * 1000)
        return CrawlResponse(
            url=url,
            status_code=None,
            content=b"",
            text="",
            headers={},
            duration_ms=duration_ms,
            error=last_error,
        )
    
    def get(self, url: str, **kwargs) -> CrawlResponse:
        """Convenience method for GET requests."""
        return self.fetch(url, method="GET", **kwargs)
    
    def post(self, url: str, **kwargs) -> CrawlResponse:
        """Convenience method for POST requests."""
        return self.fetch(url, method="POST", **kwargs)