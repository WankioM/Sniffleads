# apps/crawler/rate_limit.py

import time
import logging
from urllib.parse import urlparse

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    """Get Redis client from Django settings."""
    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


class RateLimiter:
    """
    Per-domain rate limiting using Redis.
    Uses sliding window algorithm to enforce requests per minute.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 10,
        redis_client: redis.Redis | None = None,
    ):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.redis = redis_client or get_redis_client()
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def _get_key(self, domain: str) -> str:
        """Generate Redis key for domain."""
        return f"ratelimit:{domain}"
    
    def check(self, url: str) -> tuple[bool, float]:
        """
        Check if request is allowed.
        Returns (allowed, wait_seconds).
        """
        domain = self._get_domain(url)
        key = self._get_key(domain)
        now = time.time()
        window_start = now - self.window_seconds
        
        try:
            # Count requests in current window
            self.redis.zremrangebyscore(key, 0, window_start)
            current_count = self.redis.zcard(key)
            
            if current_count < self.requests_per_minute:
                return True, 0.0
            
            # Calculate wait time until oldest request expires
            oldest = self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                wait_time = (oldest_time + self.window_seconds) - now
                return False, max(0.0, wait_time)
            
            return True, 0.0
            
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            # Fail open — allow request if Redis is down
            return True, 0.0
    
    def record(self, url: str) -> None:
        """Record a request for rate limiting."""
        domain = self._get_domain(url)
        key = self._get_key(domain)
        now = time.time()
        
        try:
            pipe = self.redis.pipeline()
            # Add current request to sorted set
            pipe.zadd(key, {f"{now}": now})
            # Clean old entries
            pipe.zremrangebyscore(key, 0, now - self.window_seconds)
            # Set TTL to auto-cleanup
            pipe.expire(key, self.window_seconds * 2)
            pipe.execute()
        except redis.RedisError as e:
            logger.error(f"Redis error recording request: {e}")
    
    def wait_if_needed(self, url: str) -> float:
        """
        Wait if rate limited, then record the request.
        Returns actual wait time in seconds.
        """
        allowed, wait_time = self.check(url)
        
        if not allowed and wait_time > 0:
            logger.debug(f"Rate limited for {self._get_domain(url)}, waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        self.record(url)
        return wait_time
    
    def get_stats(self, url: str) -> dict:
        """Get current rate limit stats for a domain."""
        domain = self._get_domain(url)
        key = self._get_key(domain)
        now = time.time()
        
        try:
            self.redis.zremrangebyscore(key, 0, now - self.window_seconds)
            count = self.redis.zcard(key)
            return {
                "domain": domain,
                "requests_in_window": count,
                "limit": self.requests_per_minute,
                "remaining": max(0, self.requests_per_minute - count),
            }
        except redis.RedisError:
            return {"domain": domain, "error": "Redis unavailable"}


class DomainRateLimiters:
    """
    Manages per-domain rate limiters with different limits.
    Uses SiteConfig.requests_per_minute for custom limits.
    """
    
    def __init__(self, default_rpm: int = 10):
        self.default_rpm = default_rpm
        self.redis = get_redis_client()
        self._limiters: dict[str, RateLimiter] = {}
    
    def get_limiter(self, domain: str, requests_per_minute: int | None = None) -> RateLimiter:
        """Get or create rate limiter for domain."""
        rpm = requests_per_minute or self.default_rpm
        cache_key = f"{domain}:{rpm}"
        
        if cache_key not in self._limiters:
            self._limiters[cache_key] = RateLimiter(
                requests_per_minute=rpm,
                redis_client=self.redis,
            )
        
        return self._limiters[cache_key]
    
    def wait_if_needed(self, url: str, requests_per_minute: int | None = None) -> float:
        """Convenience method to wait and record for a URL."""
        domain = urlparse(url).netloc.lower()
        limiter = self.get_limiter(domain, requests_per_minute)
        return limiter.wait_if_needed(url)