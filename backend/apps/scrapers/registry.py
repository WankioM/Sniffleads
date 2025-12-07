# apps/scrapers/registry.py

"""
Scraper registry - auto-registers all available crawlers and parsers.
Import this module to ensure all scrapers are registered.
"""

from apps.crawler.base import CrawlerRegistry
from apps.common.enums import SourceType

# Import scrapers to register them
from .medium import MediumCrawler, MediumParser
from .reddit import RedditCrawler, RedditParser


def register_all():
    """Register all available crawlers and parsers."""
    
    # Medium (requires Playwright due to Cloudflare)
    CrawlerRegistry.register_crawler(SourceType.MEDIUM, MediumCrawler)
    CrawlerRegistry.register_parser("medium.com", MediumParser)
    
    # Reddit (uses public JSON API)
    CrawlerRegistry.register_crawler(SourceType.REDDIT, RedditCrawler)
    CrawlerRegistry.register_parser("reddit.com", RedditParser)


# Auto-register when module is imported
register_all()