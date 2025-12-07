# apps/scrapers/medium.py

import re
import json
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from apps.sources.models import SiteConfig
from apps.crawler.base import BaseCrawler, BaseParser, ParsedLead, ParseResult

logger = logging.getLogger(__name__)


class MediumParser(BaseParser):
    """
    Parser for Medium.com pages.
    Extracts author information from profile and article pages.
    """
    
    @property
    def source_domain(self) -> str:
        return "medium.com"
    
    def parse(self, html: str, url: str) -> ParseResult:
        """Parse Medium page and extract leads + links."""
        soup = BeautifulSoup(html, "lxml")
        leads = []
        links = []
        errors = []
        
        try:
            # Determine page type and extract accordingly
            if "/@" in url or self._is_profile_page(soup):
                lead = self._parse_profile_page(soup, url)
                if lead:
                    leads.append(lead)
            else:
                # Article or listing page — extract author and find more links
                lead = self._parse_article_author(soup, url)
                if lead:
                    leads.append(lead)
            
            # Find links to follow (profiles and articles)
            links = self._extract_links(soup, url)
            
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
            errors.append(str(e))
        
        return ParseResult(leads=leads, links=links, errors=errors)
    
    def _is_profile_page(self, soup: BeautifulSoup) -> bool:
        """Check if this is a user profile page."""
        # Profile pages typically have specific meta tags or structure
        og_type = soup.find("meta", property="og:type")
        if og_type and og_type.get("content") == "profile":
            return True
        return False
    
    def _parse_profile_page(self, soup: BeautifulSoup, url: str) -> ParsedLead | None:
        """Extract lead data from a Medium profile page."""
        try:
            # Try to get name from various sources
            name = self._extract_name(soup)
            if not name:
                return None
            
            # Extract other fields
            bio = self._extract_bio(soup)
            follower_count = self._extract_follower_count(soup)
            
            # Get profile URL (normalize it)
            profile_url = self._normalize_profile_url(url)
            
            # Extract any links (Twitter, website, etc.)
            external_links = self._extract_external_links(soup)
            
            return ParsedLead(
                name=name,
                profile_url=profile_url,
                source_domain=self.source_domain,
                role=bio[:200] if bio else "",  # Use bio as role/title
                tags=self._extract_tags_from_page(soup),
                raw_data={
                    "bio": bio,
                    "follower_count": follower_count,
                    "external_links": external_links,
                    "scraped_from": url,
                },
            )
        except Exception as e:
            logger.error(f"Error parsing profile {url}: {e}")
            return None
    
    def _parse_article_author(self, soup: BeautifulSoup, url: str) -> ParsedLead | None:
        """Extract author info from an article page."""
        try:
            # Look for author link/info in article
            author_link = soup.find("a", {"data-testid": "authorName"})
            if not author_link:
                # Try alternate selectors
                author_link = soup.select_one('a[rel="author"]')
            if not author_link:
                # Try finding in JSON-LD
                return self._parse_from_json_ld(soup, url)
            
            name = author_link.get_text(strip=True)
            href = author_link.get("href", "")
            
            if not name or not href:
                return None
            
            profile_url = urljoin(url, href)
            profile_url = self._normalize_profile_url(profile_url)
            
            return ParsedLead(
                name=name,
                profile_url=profile_url,
                source_domain=self.source_domain,
                raw_data={"scraped_from": url},
            )
        except Exception as e:
            logger.error(f"Error parsing article author from {url}: {e}")
            return None
    
    def _parse_from_json_ld(self, soup: BeautifulSoup, url: str) -> ParsedLead | None:
        """Try to extract author from JSON-LD structured data."""
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    author = data.get("author")
                    if isinstance(author, dict):
                        name = author.get("name")
                        author_url = author.get("url", "")
                        if name:
                            return ParsedLead(
                                name=name,
                                profile_url=author_url or url,
                                source_domain=self.source_domain,
                                raw_data={"json_ld": data, "scraped_from": url},
                            )
            except json.JSONDecodeError:
                continue
        return None
    
    def _extract_name(self, soup: BeautifulSoup) -> str:
        """Extract user name from profile page."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "")
            # Clean up "Name – Medium" format
            if " – Medium" in title:
                return title.replace(" – Medium", "").strip()
            if " - Medium" in title:
                return title.replace(" - Medium", "").strip()
            return title.strip()
        
        # Try h1 or h2
        for tag in ["h1", "h2"]:
            header = soup.find(tag)
            if header:
                text = header.get_text(strip=True)
                if text and len(text) < 100:  # Sanity check
                    return text
        
        return ""
    
    def _extract_bio(self, soup: BeautifulSoup) -> str:
        """Extract user bio/description."""
        # Try meta description
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            return meta_desc.get("content", "").strip()
        
        # Try og:description
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            return og_desc.get("content", "").strip()
        
        return ""
    
    def _extract_follower_count(self, soup: BeautifulSoup) -> int | None:
        """Try to extract follower count."""
        # Look for text containing "followers"
        text = soup.get_text()
        match = re.search(r"([\d,\.]+[KkMm]?)\s*[Ff]ollowers", text)
        if match:
            count_str = match.group(1).replace(",", "")
            try:
                if "K" in count_str or "k" in count_str:
                    return int(float(count_str.replace("K", "").replace("k", "")) * 1000)
                if "M" in count_str or "m" in count_str:
                    return int(float(count_str.replace("M", "").replace("m", "")) * 1000000)
                return int(count_str)
            except ValueError:
                pass
        return None
    
    def _extract_external_links(self, soup: BeautifulSoup) -> list[str]:
        """Extract external links (Twitter, website, etc.)."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(domain in href for domain in ["twitter.com", "linkedin.com", "github.com"]):
                links.append(href)
            elif href.startswith("http") and "medium.com" not in href:
                # Might be personal website
                links.append(href)
        return list(set(links))[:10]  # Dedupe and limit
    
    def _extract_tags_from_page(self, soup: BeautifulSoup) -> list[str]:
        """Extract topic tags from the page."""
        tags = []
        # Look for tag links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/tag/" in href:
                tag = href.split("/tag/")[-1].split("?")[0].strip("/")
                if tag:
                    tags.append(tag)
        return list(set(tags))[:20]
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract links to follow (profiles and articles)."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            
            # Only follow medium.com links
            if "medium.com" not in full_url:
                continue
            
            # Skip non-content links
            if any(skip in full_url for skip in ["/search", "/plans", "/signin", "/signup", "?", "#"]):
                continue
            
            # Prioritize profile links
            if "/@" in full_url or "/tag/" in full_url:
                links.append(full_url.split("?")[0])  # Remove query params
        
        return list(set(links))[:50]  # Dedupe and limit
    
    def _normalize_profile_url(self, url: str) -> str:
        """Normalize profile URL to consistent format."""
        # Remove query params and fragments
        url = url.split("?")[0].split("#")[0]
        
        # Ensure it ends without trailing slash
        url = url.rstrip("/")
        
        return url


class MediumCrawler(BaseCrawler):
    """Crawler for Medium.com."""
    
    def __init__(self, site_config: SiteConfig):
        super().__init__(site_config)
        self._parser = MediumParser()
    
    @property
    def parser(self) -> BaseParser:
        return self._parser
    
    def get_headers(self) -> dict[str, str]:
        """Medium-specific headers."""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    
    def get_start_urls(self) -> list[str]:
        """Get start URLs from config, with tag URL generation."""
        urls = list(self.site_config.start_urls or [])
        
        # Generate tag URLs from filters
        filters = self.site_config.filters or {}
        tags = filters.get("tags", [])
        
        for tag in tags:
            tag_url = f"https://medium.com/tag/{tag}"
            if tag_url not in urls:
                urls.append(tag_url)
        
        return urls
    
    def should_follow(self, url: str) -> bool:
        """Determine if URL should be followed."""
        if not super().should_follow(url):
            return False
        
        # Prioritize profiles and tags
        if "/@" in url or "/tag/" in url:
            return True
        
        # Follow articles (they have author info)
        parsed = urlparse(url)
        path = parsed.path
        
        # Skip certain paths
        skip_paths = ["/m/", "/plans", "/membership", "/about", "/help"]
        if any(skip in path for skip in skip_paths):
            return False
        
        return True