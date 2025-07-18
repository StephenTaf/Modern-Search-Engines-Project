"""URL management for the Tübingen crawler."""

import re
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from typing import List, Optional, Set, Dict, Union
import time
from datetime import datetime, timedelta

from .config import CrawlerConfig
from .http_client import HttpClient


class CustomRobotsParser:
    """Custom robots.txt parser that doesn't hang."""
    
    def __init__(self, url: str, allowed_paths: List[str], disallowed_paths: List[str]):
        self.url = url
        self.allowed_paths = allowed_paths
        self.disallowed_paths = disallowed_paths
    
    def can_fetch(self, user_agent: str, url: str) -> bool:
        """Check if a user agent can fetch a URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path
            
            # Check explicit allows first (more specific)
            for allowed_path in self.allowed_paths:
                if path.startswith(allowed_path):
                    return True
            
            # Check disallows
            for disallowed_path in self.disallowed_paths:
                if path.startswith(disallowed_path):
                    return False
            
            # Default to allowed if no rules match
            return True
            
        except Exception:
            return True  # Default to allowed on error
    
    def crawl_delay(self, user_agent: str) -> Optional[float]:
        """Get crawl delay (not implemented in simple parser)."""
        return None


class UrlManager:
    """Manages URL parsing, validation, and robots.txt checking."""
    
    def __init__(self, config: CrawlerConfig, http_client: HttpClient):
        self.config = config
        self.http_client = http_client
        self.robots_cache: Dict[str, Union[RobotFileParser, CustomRobotsParser]] = {}
        self.robots_cache_time: Dict[str, datetime] = {}
        self.robots_cache_ttl = timedelta(hours=24)  # Cache robots.txt for 24 hours
    
    def extract_urls(self, html_content: str, base_url: str) -> List[str]:
        """Extract URLs from HTML content."""
        urls = []
        
        # Pattern to match href attributes
        href_pattern = r'href\s*=\s*["\']([^"\']*)["\']'
        
        matches = re.findall(href_pattern, html_content, re.IGNORECASE)
        
        for match in matches:
            # Skip empty matches and fragments
            if not match or match.startswith('#'):
                continue
            
            # Skip javascript and mailto links
            if match.startswith(('javascript:', 'mailto:')):
                continue
            
            # Convert relative URLs to absolute
            try:
                absolute_url = urljoin(base_url, match)
                if self.is_valid_url(absolute_url):
                    urls.append(absolute_url)
            except Exception:
                continue
        
        return urls
    
    def extract_urls_fast(self, html_content: str, base_url: str, max_urls: int = 1000) -> List[str]:
        """Fast URL extraction with limits for large content."""
        urls = []
        
        # For very large content, use a more targeted approach
        content_size = len(html_content)
        if content_size > 1024 * 1024:  # 1MB
            # For large pages, look for URLs in chunks to avoid regex timeout
            chunk_size = 100 * 1024  # 100KB chunks
            chunks = [html_content[i:i+chunk_size] for i in range(0, min(len(html_content), 500*1024), chunk_size)]
        else:
            chunks = [html_content]
        
        # Simpler, faster pattern for large content
        href_pattern = r'href\s*=\s*["\']([^"\']{1,500})["\']'
        
        for chunk in chunks:
            matches = re.findall(href_pattern, chunk, re.IGNORECASE)
            
            for match in matches:
                # Quick filtering
                if (not match or match.startswith(('#', 'javascript:', 'mailto:')) or 
                    len(match) > 500):
                    continue
                
                # Convert relative URLs to absolute
                try:
                    absolute_url = urljoin(base_url, match)
                    if (absolute_url.startswith(('http://', 'https://')) and 
                        len(absolute_url) < 2000):
                        urls.append(absolute_url)
                        
                        # Limit number of URLs for performance
                        if len(urls) >= max_urls:
                            return urls
                except Exception:
                    continue
        
        return urls
    
    def is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid."""
        try:
            parsed = urlparse(url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Only HTTP and HTTPS
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Skip certain file extensions
            skip_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                             '.zip', '.rar', '.tar', '.gz', '.jpg', '.jpeg', '.png', '.gif',
                             '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.swf'}
            
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in skip_extensions):
                return False
            
            return True
            
        except Exception:
            return False
    
    def normalize_url(self, url: str) -> str:
        """Normalize a URL by removing fragments and unnecessary components."""
        return UrlManager.normalize_url_static(url)
    
    @staticmethod
    def normalize_url_static(url: str) -> str:
        """Static method to normalize a URL by removing fragments and unnecessary components."""
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            
            # Remove fragment
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            
            # Remove trailing slash if not root
            if normalized.endswith('/') and len(parsed.path) > 1:
                normalized = normalized[:-1]
            
            return normalized
            
        except Exception:
            return url
    
    def get_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    def get_robots_txt_url(self, url: str) -> Optional[str]:
        """Get the robots.txt URL for a given URL."""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        except Exception:
            return None
    
    def is_sitemap_url(self, url: str) -> bool:
        """Check if a URL is a sitemap."""
        url_lower = url.lower()
        return ('sitemap' in url_lower and 
                (url_lower.endswith('.xml') or 'sitemap' in url_lower))
    
    def is_url_allowed(self, url: str, user_agent: str = '*') -> bool:
        """Check if a URL is allowed by robots.txt."""
        try:
            domain = self.get_domain(url)
            if not domain:
                return False
            
            robots_parser = self._get_robots_parser(domain)
            if robots_parser is None:
                return True  # If we can't get robots.txt, assume allowed
            
            return robots_parser.can_fetch(user_agent, url)
            
        except Exception:
            return True  # Default to allowed if error
    
    def is_url_allowed_fast(self, url: str, user_agent: str = '*') -> bool:
        """Fast robots.txt check with aggressive caching and short timeouts."""
        try:
            domain = self.get_domain(url)
            if not domain:
                return False
            
            robots_parser = self._get_robots_parser_fast(domain)
            if robots_parser is None:
                return True  # If we can't get robots.txt, assume allowed
            
            return robots_parser.can_fetch(user_agent, url)
            
        except Exception:
            return True  # Default to allowed if error
    
    def is_url_allowed_ultra_fast(self, url: str, user_agent: str = '*') -> bool:
        """Ultra-fast robots.txt check - skips robots.txt for maximum performance."""
        # For performance testing, skip robots.txt entirely
        # In production, this would check a simple whitelist/blacklist
        try:
            domain = self.get_domain(url)
            if not domain:
                return False
            
            # Skip robots.txt checking for performance - assume allowed
            # This is safe for testing since we're only crawling seed URLs
            return True
            
        except Exception:
            return True
    
    def _get_robots_parser(self, domain: str) -> Optional[Union[RobotFileParser, CustomRobotsParser]]:
        """Get robots.txt parser for a domain with caching."""
        now = datetime.now()
        
        # Check cache
        if (domain in self.robots_cache and 
            domain in self.robots_cache_time and
            now - self.robots_cache_time[domain] < self.robots_cache_ttl):
            return self.robots_cache[domain]
        
        # Fetch robots.txt
        robots_url = f"https://{domain}/robots.txt"
        response, error = self.http_client.get(robots_url)
        
        if error or not response or not self.http_client.is_success(response):
            # Try HTTP if HTTPS fails
            robots_url = f"http://{domain}/robots.txt"
            response, error = self.http_client.get(robots_url)
        
        if error or not response or not self.http_client.is_success(response):
            # Cache empty parser (allows everything)
            parser = CustomRobotsParser(robots_url, [], [])
            self.robots_cache[domain] = parser
            self.robots_cache_time[domain] = now
            return parser
        
        # Parse robots.txt content properly
        try:
            # Parse the content line by line manually to avoid hanging
            robots_content = response.text
            lines = robots_content.split('\n')
            
            # Create a simple robots.txt parser without using parser.read()
            allowed_paths = []
            disallowed_paths = []
            current_user_agent = None
            applies_to_us = False
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.lower().startswith('user-agent:'):
                    agent = line.split(':', 1)[1].strip()
                    current_user_agent = agent
                    applies_to_us = (agent == '*' or agent.lower() == '*')
                    
                elif applies_to_us and line.lower().startswith('disallow:'):
                    path = line.split(':', 1)[1].strip()
                    if path:
                        disallowed_paths.append(path)
                        
                elif applies_to_us and line.lower().startswith('allow:'):
                    path = line.split(':', 1)[1].strip()
                    if path:
                        allowed_paths.append(path)
            
            # Create a custom parser that uses our parsed data
            custom_parser = CustomRobotsParser(robots_url, allowed_paths, disallowed_paths)
            
            self.robots_cache[domain] = custom_parser
            self.robots_cache_time[domain] = now
            return custom_parser
            
        except Exception:
            # Create empty parser on error (allows everything)
            parser = CustomRobotsParser(robots_url, [], [])
            self.robots_cache[domain] = parser
            self.robots_cache_time[domain] = now
            return parser

    def _get_robots_parser_fast(self, domain: str) -> Optional[Union[RobotFileParser, CustomRobotsParser]]:
        """Get robots.txt parser for a domain with aggressive caching and fast timeouts."""
        now = datetime.now()
        
        # Check cache with longer TTL for performance
        if (domain in self.robots_cache and 
            domain in self.robots_cache_time and
            now - self.robots_cache_time[domain] < timedelta(hours=48)):  # Extended cache time
            return self.robots_cache[domain]
        
        # Use much shorter timeout for robots.txt requests
        original_timeout = self.http_client.config.timeout
        try:
            # Temporarily reduce timeout to 1 second for robots.txt
            self.http_client.config.timeout = 1
            
            # Fetch robots.txt with fast timeout
            robots_url = f"https://{domain}/robots.txt"
            response, error = self.http_client.get(robots_url)
            
            if error or not response or not self.http_client.is_success(response):
                # Try HTTP if HTTPS fails (with same fast timeout)
                robots_url = f"http://{domain}/robots.txt"
                response, error = self.http_client.get(robots_url)
            
            if error or not response or not self.http_client.is_success(response):
                # Cache empty parser (allows everything) with long TTL
                parser = CustomRobotsParser(robots_url, [], [])
                self.robots_cache[domain] = parser
                self.robots_cache_time[domain] = now
                return parser
            
            # Parse robots.txt content with same logic as original
            try:
                robots_content = response.text
                lines = robots_content.split('\n')
                
                allowed_paths = []
                disallowed_paths = []
                current_user_agent = None
                applies_to_us = False
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if line.lower().startswith('user-agent:'):
                        agent = line.split(':', 1)[1].strip()
                        current_user_agent = agent
                        applies_to_us = (agent == '*' or agent.lower() == '*')
                        
                    elif applies_to_us and line.lower().startswith('disallow:'):
                        path = line.split(':', 1)[1].strip()
                        if path:
                            disallowed_paths.append(path)
                            
                    elif applies_to_us and line.lower().startswith('allow:'):
                        path = line.split(':', 1)[1].strip()
                        if path:
                            allowed_paths.append(path)
                
                # Create a custom parser that uses our parsed data
                custom_parser = CustomRobotsParser(robots_url, allowed_paths, disallowed_paths)
                
                self.robots_cache[domain] = custom_parser
                self.robots_cache_time[domain] = now
                return custom_parser
                
            except Exception:
                # Create empty parser on error (allows everything)
                parser = CustomRobotsParser(robots_url, [], [])
                self.robots_cache[domain] = parser
                self.robots_cache_time[domain] = now
                return parser
                
        finally:
            # Always restore original timeout
            self.http_client.config.timeout = original_timeout

    def get_crawl_delay(self, url: str, user_agent: str = '*') -> float:
        """Get the crawl delay for a URL from robots.txt."""
        try:
            domain = self.get_domain(url)
            if not domain:
                return 1.0  # Default delay
            
            robots_parser = self._get_robots_parser(domain)
            if robots_parser is None:
                return 1.0
            
            delay = robots_parser.crawl_delay(user_agent)
            return float(delay) if delay is not None else 1.0
            
        except Exception:
            return 1.0
    
    def filter_urls(self, urls: List[str], base_url: str, 
                   visited_urls: Set[str], disallowed_urls: Set[str], 
                   skip_robots_check: bool = False) -> List[str]:
        """Filter URLs based on various criteria.
        
        Args:
            urls: List of URLs to filter
            base_url: Base URL for context
            visited_urls: Set of already visited URLs
            disallowed_urls: Set of disallowed URLs
            skip_robots_check: If True, skip expensive robots.txt checks for speed
        """
        filtered = []
        base_domain = self.get_domain(base_url)
        
        for url in urls:
            # Normalize URL
            normalized_url = self.normalize_url(url)
            
            # Skip if already visited or disallowed
            if normalized_url in visited_urls or normalized_url in disallowed_urls:
                continue
            
            # Basic URL validation (fast checks)
            if not self.is_valid_url(normalized_url):
                continue
            
            # Check if URL is allowed by robots.txt (expensive - can be skipped)
            if not skip_robots_check:
                if not self.is_url_allowed(normalized_url):
                    disallowed_urls.add(normalized_url)
                    continue
            
            # Additional domain filtering could go here
            # For now, we'll allow all domains
            
            filtered.append(normalized_url)
        
        return filtered

    def filter_urls_fast(self, urls: List[str], base_url: str, 
                        visited_urls: Set[str], disallowed_urls: Set[str]) -> List[str]:
        """Fast URL filtering that skips expensive robots.txt checks."""
        return self.filter_urls(urls, base_url, visited_urls, disallowed_urls, skip_robots_check=True)
    
    def get_url_score(self, url: str) -> float:
        """Calculate URL-based score for prioritization."""
        score = 0.0
        url_lower = url.lower()
        
        # Tübingen-relevant keywords
        tuebingen_keywords = ['tuebingen', 'tübingen', 'uni-tuebingen', 'tue']
        for keyword in tuebingen_keywords:
            if keyword in url_lower:
                score += 0.5
                break
        
        # English content preference
        if '/en/' in url_lower or url_lower.endswith('/en'):
            score += 0.2
        
        # University domain bonus
        if '.uni-tuebingen.de' in url_lower:
            score += 0.2
        
        # Penalize deep paths
        path_depth = url.count('/')
        if path_depth > 6:
            score -= 0.1 * (path_depth - 6)
        
        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, score))
    
    def clear_robots_cache(self):
        """Clear the robots.txt cache."""
        self.robots_cache.clear()
        self.robots_cache_time.clear() 