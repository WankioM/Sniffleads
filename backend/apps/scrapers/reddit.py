# apps/scrapers/reddit.py

import json
import logging
from urllib.parse import urljoin

from apps.sources.models import SiteConfig
from apps.crawler.base import BaseCrawler, BaseParser, ParsedLead, ParseResult

logger = logging.getLogger(__name__)


class RedditParser(BaseParser):
    """
    Parser for Reddit JSON API responses.
    Extracts user information from subreddit posts and comments.
    """
    
    @property
    def source_domain(self) -> str:
        return "reddit.com"
    
    def parse(self, html: str, url: str) -> ParseResult:
        """Parse Reddit JSON response and extract leads + links."""
        leads = []
        links = []
        errors = []
        
        try:
            # Reddit .json endpoints return JSON, not HTML
            data = json.loads(html)
            
            # Handle different response structures
            if isinstance(data, list):
                # Subreddit listing returns [listing, ...]
                for item in data:
                    if isinstance(item, dict) and "data" in item:
                        self._extract_from_listing(item["data"], leads, links)
            elif isinstance(data, dict) and "data" in data:
                self._extract_from_listing(data["data"], leads, links)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {url}: {e}")
            errors.append(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
            errors.append(str(e))
        
        return ParseResult(leads=leads, links=links, errors=errors)
    
    def _extract_from_listing(self, data: dict, leads: list, links: list) -> None:
        """Extract leads from a Reddit listing data structure."""
        children = data.get("children", [])
        
        for child in children:
            kind = child.get("kind", "")
            child_data = child.get("data", {})
            
            if kind == "t3":  # Post
                lead = self._extract_from_post(child_data)
                if lead:
                    leads.append(lead)
                    
                # Add link to comments for more users
                permalink = child_data.get("permalink", "")
                if permalink:
                    links.append(f"https://www.reddit.com{permalink}.json?limit=100")
                    
            elif kind == "t1":  # Comment
                lead = self._extract_from_comment(child_data)
                if lead:
                    leads.append(lead)
                    
                # Recurse into replies
                replies = child_data.get("replies", "")
                if isinstance(replies, dict) and "data" in replies:
                    self._extract_from_listing(replies["data"], leads, links)
        
        # Handle pagination
        after = data.get("after")
        if after:
            # We'll handle this in the crawler
            pass
    
    def _extract_from_post(self, data: dict) -> ParsedLead | None:
        """Extract lead from a Reddit post."""
        author = data.get("author", "")
        
        # Skip deleted/removed users
        if not author or author in ("[deleted]", "[removed]", "AutoModerator"):
            return None
        
        profile_url = f"https://www.reddit.com/user/{author}"
        
        return ParsedLead(
            name=author,
            profile_url=profile_url,
            source_domain=self.source_domain,
            role="Reddit User",
            raw_data={
                "subreddit": data.get("subreddit", ""),
                "post_title": data.get("title", "")[:200],
                "post_score": data.get("score", 0),
                "post_id": data.get("id", ""),
                "created_utc": data.get("created_utc", 0),
                "is_post_author": True,
            },
        )
    
    def _extract_from_comment(self, data: dict) -> ParsedLead | None:
        """Extract lead from a Reddit comment."""
        author = data.get("author", "")
        
        if not author or author in ("[deleted]", "[removed]", "AutoModerator"):
            return None
        
        profile_url = f"https://www.reddit.com/user/{author}"
        
        return ParsedLead(
            name=author,
            profile_url=profile_url,
            source_domain=self.source_domain,
            role="Reddit User",
            raw_data={
                "subreddit": data.get("subreddit", ""),
                "comment_score": data.get("score", 0),
                "comment_id": data.get("id", ""),
                "created_utc": data.get("created_utc", 0),
                "is_post_author": False,
            },
        )


class RedditCrawler(BaseCrawler):
    """
    Crawler for Reddit using public JSON API.
    
    Reddit allows appending .json to most URLs to get JSON responses.
    No authentication required for public data.
    """
    
    def __init__(self, site_config: SiteConfig):
        super().__init__(site_config)
        self._parser = RedditParser()
    
    @property
    def parser(self) -> BaseParser:
        return self._parser
    
    def get_headers(self) -> dict[str, str]:
        """Reddit-specific headers."""
        return {
            # Reddit requires a descriptive User-Agent
            "User-Agent": "SniffLeads/1.0 (Lead Discovery Tool)",
            "Accept": "application/json",
        }
    
    def get_start_urls(self) -> list[str]:
        """Generate subreddit JSON URLs from config."""
        urls = []
        
        # Use start_urls if provided
        for url in (self.site_config.start_urls or []):
            urls.append(self._to_json_url(url))
        
        # Generate from filters
        filters = self.site_config.filters or {}
        subreddits = filters.get("subreddits", [])
        sort = filters.get("sort", "hot")  # hot, new, top, rising
        limit = filters.get("limit", 25)
        
        for subreddit in subreddits:
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
            if url not in urls:
                urls.append(url)
        
        return urls
    
    def _to_json_url(self, url: str) -> str:
        """Convert Reddit URL to JSON endpoint."""
        # Remove trailing slash
        url = url.rstrip("/")
        
        # Add .json if not present
        if not url.endswith(".json"):
            # Handle URLs with query params
            if "?" in url:
                base, params = url.split("?", 1)
                url = f"{base}.json?{params}"
            else:
                url = f"{url}.json"
        
        return url
    
    def should_follow(self, url: str) -> bool:
        """Only follow Reddit JSON URLs."""
        if not super().should_follow(url):
            return False
        
        # Must be a JSON endpoint
        if ".json" not in url:
            return False
        
        # Skip user profile pages (we just want the username)
        if "/user/" in url:
            return False
        
        return True