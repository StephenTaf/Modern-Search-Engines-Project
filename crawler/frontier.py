"""Frontier management for the Tübingen crawler."""

import time
import threading
from heapdict import heapdict
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from .config import CrawlerConfig
from .database import DatabaseManager
from .scoring import ContentScorer
from .url_manager import UrlManager


@dataclass
class FrontierEntry:
    url: str
    schedule_time: float
    delay: float
    priority: float
    linking_depth: int
    domain_linking_depth: int
    parent_url: Optional[str] = None
    added_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.added_time is None:
            self.added_time = datetime.now()


class FrontierManager:
    """Manages the crawler frontier with priority scheduling and delay handling."""
    
    def __init__(self, config: CrawlerConfig, db_manager: DatabaseManager, scorer: ContentScorer):
        self.config = config
        self.db_manager = db_manager
        self.scorer = scorer
        
        # priority queue
        self.frontier: heapdict = heapdict()
        self.frontier_data: Dict[str, FrontierEntry] = {}
        
        # Visited URLs tracking
        self.visited_urls: Set[str] = set()
        self.crawled_urls: Set[str] = set()
        
        self.domain_delays: Dict[str, float] = {}
        self.last_access_time: Dict[str, float] = {}
        
        # Track pages crawled per domain to improve document diversity
        self.domain_page_counts: Dict[str, int] = {}
        self._domain_lock = threading.RLock()  # Thread-safe updates for multiprocessing
        
        # Statistics
        self.stats = {
            'total_added': 0,
            'total_crawled': 0,
            'total_rejected': 0,
            'domain_counts': {}
        }
    
    def should_add_to_frontier(self, url: str, parent_url: Optional[str] = None, 
                              linking_depth: int = 0, domain_linking_depth: int = 0) -> Tuple[bool, Optional[str]]:
        """
        Args:
            url: The normalized URL to check
            parent_url: The parent URL that linked to this URL
            linking_depth: How many levels deep this URL is
            domain_linking_depth: How many levels deep within the same domain
            
        Returns:
            Tuple of (should_add: bool, reason: Optional[str])
            - should_add: True if URL should be added to frontier
            - reason: Optional reason string if URL is rejected
        """ 
        # 1. Domain-specific filtering
        domain = self._get_domain(url)
        if domain:
            # Skip certain domains, which are not interesting here
            blocked_domains = {
                'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
                'youtube.com', 'tiktok.com', 'pinterest.com'
            }
            if any(blocked in domain for blocked in blocked_domains):
                return False, f"blocked_domain: {domain}"
            # Limit crawling depth per domain
            domain_page_count = self.get_domain_page_count(domain)
            if domain_page_count > 1000:  # This was set empiricaly
                return False, f"domain_limit_exceeded: {domain} ({domain_page_count} pages)"
        
        # 2. URL pattern filtering
        url_lower = url.lower()
        
        # Don't need non-text files
        if any(url_lower.endswith(ext) for ext in [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
            '.mp3', '.mp4', '.wav', '.avi', '.mov',
            '.zip', '.rar', '.tar', '.gz',
            '.css', '.js', '.json', '.xml', '.rss'
        ]):
            return False, "non_html_content"
        
        # Skip URLs with non-document patterns (from experiments)
        skip_patterns = [
            '/admin/', '/login/', '/logout/', '/register/',
            '/api/', '/ajax/', '/json/', '/download/',
            'mailto:', 'tel:', 'ftp:', 'javascript:',
            '/wp-content/', '/wp-admin/',
            '?action=', '&action=', '/search?', '?search=',
            '/cart/', '/checkout/', '/payment/'
        ]
        if any(pattern in url_lower for pattern in skip_patterns):
            return False, f"pattern_match: {next(p for p in skip_patterns if p in url_lower)}"
        
        # Filter if document is too deep
        if linking_depth > 8:  # Customize this limit
            return False, f"max_depth_exceeded: {linking_depth}"
        
        # URL length filtering should be reasonable
        if len(url) > 2000:  # Customize this limit
            return False, f"url_too_long: {len(url)} chars"
        
        #  Query parameter filtering
        if '?' in url:
            # Count query parameters
            query_params = url.split('?', 1)[1].count('&') + 1
            if query_params > 10:  # Customize this limit
                return False, f"too_many_params: {query_params}"
        
        # If all checks pass, allow adding to frontier :D
        return True, None

    def add_url(self, url: str, parent_url: Optional[str] = None, 
                linking_depth: int = 0, domain_linking_depth: int = 0,
                priority_override: Optional[float] = None) -> bool:
        """Add a URL to the frontier."""
        # Use normalization for URL
        def normalize_url_local(url: str) -> str:
            """Local URL normalization function."""
            try:
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

        normalized_url = normalize_url_local(url)
        if not normalized_url or normalized_url == url and not url.startswith(('http://', 'https://')):
            return False
        
        # Pre-frontier validation check to avoid similar content
        should_add, rejection_reason = self.should_add_to_frontier(
            normalized_url, parent_url, linking_depth, domain_linking_depth
        )
        if not should_add:
            self.stats['total_rejected'] += 1
            if rejection_reason:
                print(f"Rejected URL: {normalized_url} - {rejection_reason}")
            return False
        
        # Skip if duplicated
        if normalized_url in self.visited_urls or normalized_url in self.crawled_urls:
            return False
        
        # Check if URL is already in frontier
        if normalized_url in self.frontier or normalized_url in self.frontier_data:
            return False
        
        # Check if URL is in database
        if self.db_manager.is_url_crawled(normalized_url):
            self.crawled_urls.add(normalized_url)
            return False
        
        # If we don't need this domain
        if self.db_manager.is_url_disallowed(normalized_url):
            self.stats['total_rejected'] += 1
            return False
        
        # May need to override priority for manual control
        if priority_override is not None:
            priority = priority_override
        else:
            # Here is how score is calculated
            parent_score = None
            if parent_url:
                normalized_parent_url = normalize_url_local(parent_url)
                parent_info = self.db_manager.get_url_info(normalized_parent_url)
                if parent_info:
                    parent_score = parent_info.get('score')
            priority = self.scorer.calculate_url_score(normalized_url, parent_url, parent_score)
        depth_penalty = max(0.0, 1.0 - (linking_depth * 0.05))
        priority *= depth_penalty
        domain = self._get_domain(normalized_url)
        if not domain:
            return False
        
        delay = self._get_domain_delay(domain)
        schedule_time = time.time()
        # Put url in queue
        entry = FrontierEntry(
            url=normalized_url,
            schedule_time=schedule_time,
            delay=delay,
            priority=priority,
            linking_depth=linking_depth,
            domain_linking_depth=domain_linking_depth,
            parent_url=parent_url
        )
        self.frontier[normalized_url] = -priority
        self.frontier_data[normalized_url] = entry
        
        # Statistics
        self.stats['total_added'] += 1
        if domain not in self.stats['domain_counts']:
            self.stats['domain_counts'][domain] = 0
        self.stats['domain_counts'][domain] += 1

        # Store in database
        self.db_manager.add_to_frontier(normalized_url, schedule_time, delay, priority)
        return True
    
    def get_next_url(self) -> Optional[Tuple[str, FrontierEntry]]:
        """Get the next URL to crawl from the frontier."""
        current_time = time.time()
        checked_urls = []
        max_checks = min(50, len(self.frontier))  # Limit to avoid infinite loops
        skip_domain_delays = self.config.enable_multiprocessing
        for _ in range(max_checks):
            if not self.frontier:
                break
                
            url, neg_priority = self.frontier.peekitem()
            # Handle case where frontier and frontier_data are out of sync
            if url not in self.frontier_data:
                print(f"Warning: URL '{url}' in frontier but not in frontier_data. Removing inconsistent entry.")
                # Remove the inconsistent entry from frontier
                del self.frontier[url]
                continue
            entry = self.frontier_data[url]
            # Check if URL is ready to be crawled
            if entry.schedule_time <= current_time:
                domain = self._get_domain(url) # If we need delay
                if skip_domain_delays or (domain and self._is_domain_ready(domain)):
                    del self.frontier[url] # remove from queue
                    del self.frontier_data[url]
                    if not skip_domain_delays and domain:
                        self.last_access_time[domain] = current_time
                    self.visited_urls.add(url) # visited
                    self.db_manager.remove_from_frontier(url)
                    for checked_url, checked_entry in checked_urls:
                        self.frontier[checked_url] = -checked_entry.priority
                    return url, entry
                else:
                    checked_urls.append((url, entry))
                    del self.frontier[url]
                    del self.frontier_data[url]
                    continue
            else:
                break
        for checked_url, checked_entry in checked_urls:
            self.frontier[checked_url] = -checked_entry.priority
        
        return None
    
    def mark_crawled(self, url: str, success: bool = True):
        self.crawled_urls.add(url)
        self.stats['total_crawled'] += 1
        if success and url in self.visited_urls:
            self.visited_urls.remove(url)

    def update_priority(self, url: str, new_priority: float):
        """Update the priority of a URL in the frontier."""
        if url in self.frontier:
            self.frontier[url] = -new_priority
            self.frontier_data[url].priority = new_priority
            entry = self.frontier_data[url]
            self.db_manager.add_to_frontier(url, entry.schedule_time, entry.delay, new_priority)
    
    def remove_url(self, url: str, reason: str = ""):
        """Remove a URL from the frontier."""
        if url in self.frontier:
            del self.frontier[url]
            del self.frontier_data[url]
            self.db_manager.remove_from_frontier(url)
            if reason:
                self.db_manager.add_disallowed_url(url, reason)
            self.stats['total_rejected'] += 1 # Statistics
    
    def get_frontier_size(self) -> int:
        return len(self.frontier)
    
    def get_domain_count(self, domain: str) -> int:
        return self.stats['domain_counts'].get(domain, 0)
    
    def get_top_urls(self, count: int = 10) -> List[Tuple[str, float]]:
        items = []
        for url, neg_priority in self.frontier.items():
            items.append((url, -neg_priority))
        
        # Sort by priority (descending!)
        items.sort(key=lambda x: x[1], reverse=True)
        
        return items[:count]
    
    def get_statistics(self) -> Dict:
        """Get frontier statistics."""
        return {
            'frontier_size': len(self.frontier),
            'visited_count': len(self.visited_urls),
            'crawled_count': len(self.crawled_urls),
            'total_added': self.stats['total_added'],
            'total_crawled': self.stats['total_crawled'],
            'total_rejected': self.stats['total_rejected'],
            'domain_counts': self.stats['domain_counts'].copy(),
            'top_domains': self._get_top_domains()
        }
    
    def clear_frontier(self):
        self.frontier.clear()
        self.frontier_data.clear()
        self.db_manager.clear_frontier()
        # Reset statistics
        self.stats = {
            'total_added': 0,
            'total_crawled': 0,
            'total_rejected': 0,
            'domain_counts': {}
        }
    
    def load_from_database(self):
        """Load frontier state from database."""
        db_frontier = self.db_manager.get_frontier_urls(limit=100_000_000)
        
        for url, schedule_time, delay, priority in db_frontier:
            entry = FrontierEntry(
                url=url,
                schedule_time=schedule_time,
                delay=delay,
                priority=priority,
                linking_depth=0,  # Will be updated if needed
                domain_linking_depth=0
            )
            
            self.frontier[url] = -priority
            self.frontier_data[url] = entry
            domain = self._get_domain(url) # Update statistics
            if domain:
                if domain not in self.stats['domain_counts']:
                    self.stats['domain_counts'][domain] = 0
                self.stats['domain_counts'][domain] += 1
        
        # Load previously crawled URLs
        self._load_crawled_urls_from_database()
        # Initialize domain page counts from database - used to keep diversity
        self._initialize_domain_counts_from_database()
    
    def _load_crawled_urls_from_database(self):
        try:
            with self.db_manager._get_connection() as conn:
                result = conn.execute("SELECT url FROM urlsDB").fetchall()
                for (url,) in result:
                    self.crawled_urls.add(url)
            print(f"Loaded {len(self.crawled_urls)} previously crawled URLs from database")
        except Exception as e:
            print(f"Error loading crawled URLs from database: {e}") # It's okay if there is an exception
    
    def save_to_database(self):
        """Save current frontier to database."""
        self.db_manager.clear_frontier()
        for url, entry in self.frontier_data.items():
            self.db_manager.add_to_frontier(
                url, entry.schedule_time, entry.delay, entry.priority
            )
    
    def _initialize_domain_counts_from_database(self):
        with self._domain_lock:
            try:
                with self.db_manager._get_connection() as conn:
                    result = conn.execute("""
                        SELECT url FROM urlsDB 
                        WHERE lastFetch IS NOT NULL
                    """).fetchall()
                    
                    self.domain_page_counts.clear()
                    
                    for (url,) in result:
                        domain = self._get_domain(url)
                        if domain:
                            self.domain_page_counts[domain] = self.domain_page_counts.get(domain, 0) + 1
                    
                    print(f"-> [SYSTEM] Initialized domain counts: {len(self.domain_page_counts)} domains")
                    if self.domain_page_counts:
                        # Show top domains
                        top_domains = sorted(self.domain_page_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                        print(f"   Top domains: {dict(top_domains)}")
                        
            except Exception as e:
                print(f"Warning: Could not initialize domain counts: {e}")
                self.domain_page_counts = {}
    
    def get_domain_page_count(self, domain: str) -> int:
        with self._domain_lock:
            return self.domain_page_counts.get(domain, 0)
    
    def update_domain_page_count(self, url: str):
        domain = self._get_domain(url)
        if domain:
            with self._domain_lock:
                self.domain_page_counts[domain] = self.domain_page_counts.get(domain, 0) + 1
                # Optional: Log when reaching milestones
                count = self.domain_page_counts[domain]
                if count in [50, 100, 200, 500]:
                    print(f"📊 Domain {domain}: {count} pages crawled")
    
    def get_domain_statistics(self) -> Dict[str, int]:
        with self._domain_lock:
            return dict(self.domain_page_counts)
    
    def _get_domain(self, url: str) -> Optional[str]:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    def _get_domain_delay(self, domain: str) -> float:
        if domain not in self.domain_delays:
            self.domain_delays[domain] = 0.1  # Not much, works fine
        
        return self.domain_delays[domain]
    
    def _is_domain_ready(self, domain: str) -> bool:
        """Check if a domain is ready for crawling (respects delay)."""
        if domain not in self.last_access_time:
            return True
        
        current_time = time.time()
        delay = self._get_domain_delay(domain)
        time_since_last_access = current_time - self.last_access_time[domain]
        
        return time_since_last_access >= delay
    
    def _get_top_domains(self, count: int = 10) -> List[Tuple[str, int]]:
        """Get top domains by URL count."""
        items = list(self.stats['domain_counts'].items())
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:count]
    
    def set_domain_delay(self, domain: str, delay: float):
        """Set the delay for a specific domain."""
        self.domain_delays[domain] = delay
    
    def get_domain_delay(self, domain: str) -> float:
        """Get the delay for a specific domain."""
        return self.domain_delays.get(domain, 1.0)
    
    def __len__(self) -> int:
        """Get the size of the frontier."""
        return len(self.frontier)
    
    def __contains__(self, url: str) -> bool:
        """Check if URL is in frontier."""
        return url in self.frontier 
