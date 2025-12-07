# apps/crawler/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import logging

from apps.sources.models import SiteConfig
from apps.leads.models import Lead

logger = logging.getLogger(__name__)


@dataclass
class ParsedLead:
    """
    Data extracted from a page, ready for upserting.
    Maps to Lead model fields.
    """
    name: str
    profile_url: str
    source_domain: str
    role: str = ""
    company: str = ""
    email: str = ""
    tags: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dict for upsert_lead()."""
        return {
            "name": self.name,
            "profile_url": self.profile_url,
            "source_domain": self.source_domain,
            "role": self.role,
            "company": self.company,
            "email": self.email,
            "tags": self.tags,
            "raw_data": self.raw_data,
        }


@dataclass
class ParseResult:
    """Result from parsing a single page."""
    leads: list[ParsedLead] = field(default_factory=list)
    links: list[str] = field(default_factory=list)  # URLs to follow
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """
    Abstract base class for page parsers.
    Each source (Medium, Reddit, etc.) implements its own parser.
    """
    
    @property
    @abstractmethod
    def source_domain(self) -> str:
        """The domain this parser handles (e.g., 'medium.com')."""
        pass
    
    @abstractmethod
    def parse(self, html: str, url: str) -> ParseResult:
        """
        Parse HTML content and extract leads + links.
        
        Args:
            html: Raw HTML content
            url: The URL this content came from
            
        Returns:
            ParseResult with extracted leads and follow links
        """
        pass
    
    def can_handle(self, url: str) -> bool:
        """Check if this parser can handle the given URL."""
        return self.source_domain in url.lower()


class BaseCrawler(ABC):
    """
    Abstract base class for crawlers.
    Handles URL generation and crawl configuration.
    """
    
    def __init__(self, site_config: SiteConfig):
        self.site_config = site_config
    
    @property
    @abstractmethod
    def parser(self) -> BaseParser:
        """Return the parser instance for this crawler."""
        pass
    
    @property
    def source_domain(self) -> str:
        """Domain this crawler targets."""
        return self.site_config.domain
    
    @property
    def requests_per_minute(self) -> int:
        """Rate limit for this crawler."""
        return self.site_config.requests_per_minute
    
    @property
    def max_pages(self) -> int:
        """Maximum pages to crawl per job."""
        return self.site_config.max_pages
    
    @property
    def use_browser(self) -> bool:
        """Whether to use headless browser."""
        return self.site_config.use_browser
    
    def get_start_urls(self) -> list[str]:
        """
        Get initial URLs to crawl.
        Default: return site_config.start_urls.
        Override for dynamic URL generation.
        """
        return self.site_config.start_urls or []
    
    def should_follow(self, url: str) -> bool:
        """
        Determine if a discovered URL should be followed.
        Override for custom filtering logic.
        """
        if not self.site_config.follow_links:
            return False
        return self.source_domain in url.lower()
    
    def filter_links(self, links: list[str], visited: set[str]) -> list[str]:
        """Filter discovered links before adding to queue."""
        return [
            link for link in links
            if link not in visited and self.should_follow(link)
        ]
    
    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        """
        Return custom headers for this crawler.
        Override to add auth tokens, cookies, etc.
        """
        pass


class CrawlerRegistry:
    """
    Registry of available crawlers.
    Maps source_type to crawler class.
    """
    
    _crawlers: dict[str, type[BaseCrawler]] = {}
    _parsers: dict[str, type[BaseParser]] = {}
    
    @classmethod
    def register_crawler(cls, source_type: str, crawler_class: type[BaseCrawler]):
        """Register a crawler class for a source type."""
        cls._crawlers[source_type] = crawler_class
        logger.info(f"Registered crawler for {source_type}: {crawler_class.__name__}")
    
    @classmethod
    def register_parser(cls, source_domain: str, parser_class: type[BaseParser]):
        """Register a parser class for a domain."""
        cls._parsers[source_domain] = parser_class
        logger.info(f"Registered parser for {source_domain}: {parser_class.__name__}")
    
    @classmethod
    def get_crawler(cls, source_type: str, site_config: SiteConfig) -> BaseCrawler | None:
        """Get crawler instance for source type."""
        crawler_class = cls._crawlers.get(source_type)
        if crawler_class:
            return crawler_class(site_config)
        return None
    
    @classmethod
    def get_parser(cls, source_domain: str) -> BaseParser | None:
        """Get parser instance for domain."""
        parser_class = cls._parsers.get(source_domain)
        if parser_class:
            return parser_class()
        return None
    
    @classmethod
    def list_crawlers(cls) -> list[str]:
        """List registered source types."""
        return list(cls._crawlers.keys())
    
    @classmethod
    def list_parsers(cls) -> list[str]:
        """List registered domains."""
        return list(cls._parsers.keys())