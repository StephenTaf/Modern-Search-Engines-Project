"""Frontier management for the Tübingen crawler."""

import time
import threading
from heapdict import heapdict
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from .config import CrawlerConfig
from .database import DatabaseManager
from .scoring import ContentScorer
from .url_manager import UrlManager


@dataclass
class FrontierEntry:
    """Represents an entry in the frontier."""
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
        
        # In-memory frontier (priority queue)
        self.frontier: heapdict = heapdict()
        self.frontier_data: Dict[str, FrontierEntry] = {}
        
        # Visited URLs tracking
        self.visited_urls: Set[str] = set()
        self.crawled_urls: Set[str] = set()
        
        # Domain delay tracking (disabled in multiprocessing mode)
        self.domain_delays: Dict[str, float] = {}
        self.last_access_time: Dict[str, float] = {}
        
        # DOMAIN TRACKING: Track pages crawled per domain
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
        Pre-frontier validation method. Override this to add custom URL filtering logic.
        
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
        
        # Example custom validations - you can modify these:
        
        # 1. Domain-specific filtering
        domain = self._get_domain(url)
        if domain:
            # Skip certain domains
            blocked_domains = {
                'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
                'youtube.com', 'tiktok.com', 'pinterest.com'
            }
            if any(blocked in domain for blocked in blocked_domains):
                return False, f"blocked_domain: {domain}"
            
            # Limit crawling depth per domain
            domain_page_count = self.get_domain_page_count(domain)
            if domain_page_count > 1000:  # Customize this limit
                return False, f"domain_limit_exceeded: {domain} ({domain_page_count} pages)"
        
        # 2. URL pattern filtering
        url_lower = url.lower()
        
        # Skip non-relevant file types
        if any(url_lower.endswith(ext) for ext in [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
            '.mp3', '.mp4', '.wav', '.avi', '.mov',
            '.zip', '.rar', '.tar', '.gz',
            '.css', '.js', '.json', '.xml', '.rss'
        ]):
            return False, "non_html_content"
        
        # Skip URLs with certain patterns
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
        
        # 3. Depth-based filtering
        if linking_depth > 8:  # Customize this limit
            return False, f"max_depth_exceeded: {linking_depth}"
        
        # 4. URL length filtering
        if len(url) > 2000:  # Customize this limit
            return False, f"url_too_long: {len(url)} chars"
        
        # 5. Query parameter filtering (optional)
        if '?' in url:
            # Count query parameters
            query_params = url.split('?', 1)[1].count('&') + 1
            if query_params > 10:  # Customize this limit
                return False, f"too_many_params: {query_params}"
        
        # If all checks pass, allow adding to frontier
        return True, None

    def add_url(self, url: str, parent_url: Optional[str] = None, 
                linking_depth: int = 0, domain_linking_depth: int = 0,
                priority_override: Optional[float] = None) -> bool:
        """Add a URL to the frontier."""
        
        # CRITICAL FIX: Normalize URL before any processing to ensure consistent keys
        from urllib.parse import urlparse, urlunparse
        
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
        
        # Skip if URL normalization failed (invalid URL)
        if not normalized_url or normalized_url == url and not url.startswith(('http://', 'https://')):
            return False
        
        # NEW: Pre-frontier validation check
        should_add, rejection_reason = self.should_add_to_frontier(
            normalized_url, parent_url, linking_depth, domain_linking_depth
        )
        if not should_add:
            self.stats['total_rejected'] += 1
            if rejection_reason:
                print(f"Rejected URL: {normalized_url} - {rejection_reason}")
            return False
        
        # Skip if already processed (check normalized URL)
        if normalized_url in self.visited_urls or normalized_url in self.crawled_urls:
            return False
        
        # CRITICAL FIX: Check if URL is already in frontier (prevent duplicates)
        if normalized_url in self.frontier or normalized_url in self.frontier_data:
            return False
        
        # Check if URL is in database (use normalized URL)
        if self.db_manager.is_url_crawled(normalized_url):
            self.crawled_urls.add(normalized_url)
            return False
        
        # Check if URL is disallowed (use normalized URL)
        if self.db_manager.is_url_disallowed(normalized_url):
            self.stats['total_rejected'] += 1
            return False
        
        # Calculate priority
        if priority_override is not None:
            priority = priority_override
        else:
            # Get parent score for contextual scoring
            parent_score = None
            if parent_url:
                # Normalize parent URL too for consistent lookup
                normalized_parent_url = normalize_url_local(parent_url)
                parent_info = self.db_manager.get_url_info(normalized_parent_url)
                if parent_info:
                    parent_score = parent_info.get('score')
            
            priority = self.scorer.calculate_url_score(normalized_url, parent_url, parent_score)
        
        # Add depth penalty
        depth_penalty = max(0.0, 1.0 - (linking_depth * 0.05))
        priority *= depth_penalty
        
        # Get domain and set delay (use normalized URL)
        domain = self._get_domain(normalized_url)
        if not domain:
            return False
        
        delay = self._get_domain_delay(domain)
        # Schedule new URLs for immediate crawling (current time)
        # Domain delays are handled in get_next_url() method
        schedule_time = time.time()
        
        # Create frontier entry with normalized URL
        entry = FrontierEntry(
            url=normalized_url,  # Store normalized URL in entry
            schedule_time=schedule_time,
            delay=delay,
            priority=priority,
            linking_depth=linking_depth,
            domain_linking_depth=domain_linking_depth,
            parent_url=parent_url
        )
        
        # CRITICAL FIX: Use normalized URL as key in both data structures
        self.frontier[normalized_url] = -priority
        self.frontier_data[normalized_url] = entry
        
        # Update statistics
        self.stats['total_added'] += 1
        if domain not in self.stats['domain_counts']:
            self.stats['domain_counts'][domain] = 0
        self.stats['domain_counts'][domain] += 1
        
        # Store in database (use normalized URL)
        self.db_manager.add_to_frontier(normalized_url, schedule_time, delay, priority)
        
        return True
    
    def get_next_url(self) -> Optional[Tuple[str, FrontierEntry]]:
        """Get the next URL to crawl from the frontier."""
        current_time = time.time()
        
        # Try to find a URL that is ready to be crawled
        checked_urls = []
        max_checks = min(50, len(self.frontier))  # Limit to avoid infinite loops
        
        # In multiprocessing mode, skip domain delay checking (handled by EfficientDomainScheduler)
        skip_domain_delays = self.config.enable_multiprocessing
        
        for _ in range(max_checks):
            if not self.frontier:
                break
                
            url, neg_priority = self.frontier.peekitem()
            
            # CRITICAL FIX: Handle case where frontier and frontier_data are out of sync
            if url not in self.frontier_data:
                print(f"Warning: URL '{url}' in frontier but not in frontier_data. Removing inconsistent entry.")
                # Remove the inconsistent entry from frontier
                del self.frontier[url]
                continue
            
            entry = self.frontier_data[url]
            
            # Check if URL is ready to be crawled (schedule time)
            if entry.schedule_time <= current_time:
                # Check domain delay (skip in multiprocessing mode)
                domain = self._get_domain(url)
                if skip_domain_delays or (domain and self._is_domain_ready(domain)):
                    # Found a ready URL - remove from frontier
                    del self.frontier[url]
                    del self.frontier_data[url]
                    
                    # Update last access time (only in single-threaded mode)
                    if not skip_domain_delays and domain:
                        self.last_access_time[domain] = current_time
                    
                    # Mark as visited
                    self.visited_urls.add(url)
                    
                    # Remove from database frontier
                    self.db_manager.remove_from_frontier(url)
                    
                    # Put back any URLs we checked but didn't use
                    for checked_url, checked_entry in checked_urls:
                        self.frontier[checked_url] = -checked_entry.priority
                    
                    return url, entry
                else:
                    # Domain not ready - remove temporarily and check next URL
                    checked_urls.append((url, entry))
                    del self.frontier[url]
                    del self.frontier_data[url]
                    continue
            else:
                # URL not ready yet (schedule time) - put back any checked URLs and stop
                break
        
        # Put back all checked URLs since none were ready
        for checked_url, checked_entry in checked_urls:
            self.frontier[checked_url] = -checked_entry.priority
        
        return None
    
    def mark_crawled(self, url: str, success: bool = True):
        """Mark a URL as crawled."""
        self.crawled_urls.add(url)
        self.stats['total_crawled'] += 1
        
        # Remove from visited if crawl was successful
        if success and url in self.visited_urls:
            self.visited_urls.remove(url)
    
    def update_priority(self, url: str, new_priority: float):
        """Update the priority of a URL in the frontier."""
        if url in self.frontier:
            self.frontier[url] = -new_priority
            self.frontier_data[url].priority = new_priority
            
            # Update in database
            entry = self.frontier_data[url]
            self.db_manager.add_to_frontier(url, entry.schedule_time, entry.delay, new_priority)
    
    def remove_url(self, url: str, reason: str = ""):
        """Remove a URL from the frontier."""
        if url in self.frontier:
            del self.frontier[url]
            del self.frontier_data[url]
            
            # Remove from database
            self.db_manager.remove_from_frontier(url)
            
            # Add to disallowed if reason provided
            if reason:
                self.db_manager.add_disallowed_url(url, reason)
            
            self.stats['total_rejected'] += 1
    
    def get_frontier_size(self) -> int:
        """Get the current size of the frontier."""
        return len(self.frontier)
    
    def get_domain_count(self, domain: str) -> int:
        """Get the number of URLs in frontier for a domain."""
        return self.stats['domain_counts'].get(domain, 0)
    
    def get_top_urls(self, count: int = 10) -> List[Tuple[str, float]]:
        """Get the top URLs by priority."""
        items = []
        for url, neg_priority in self.frontier.items():
            items.append((url, -neg_priority))
        
        # Sort by priority (descending)
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
        """Clear the frontier."""
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
        """Load frontier from database."""
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
            
            # Update statistics
            domain = self._get_domain(url)
            if domain:
                if domain not in self.stats['domain_counts']:
                    self.stats['domain_counts'][domain] = 0
                self.stats['domain_counts'][domain] += 1
        
        # Load previously crawled URLs for faster deduplication
        self._load_crawled_urls_from_database()
        
        # DOMAIN TRACKING: Initialize domain page counts from database
        self._initialize_domain_counts_from_database()
    
    def _load_crawled_urls_from_database(self):
        """Load previously crawled URLs from database into memory for faster deduplication."""
        try:
            with self.db_manager._get_connection() as conn:
                result = conn.execute("SELECT url FROM urlsDB").fetchall()
                for (url,) in result:
                    self.crawled_urls.add(url)
            print(f"Loaded {len(self.crawled_urls)} previously crawled URLs from database")
        except Exception as e:
            print(f"Error loading crawled URLs from database: {e}")
            # Not critical - database check will still work
    
    def save_to_database(self):
        """Save current frontier to database."""
        # Clear database frontier first
        self.db_manager.clear_frontier()
        
        # Save current frontier
        for url, entry in self.frontier_data.items():
            self.db_manager.add_to_frontier(
                url, entry.schedule_time, entry.delay, entry.priority
            )
    
    def _initialize_domain_counts_from_database(self):
        """Initialize domain page counts from existing crawled URLs in database."""
        with self._domain_lock:
            try:
                with self.db_manager._get_connection() as conn:
                    # Count crawled pages per domain
                    result = conn.execute("""
                        SELECT url FROM urlsDB 
                        WHERE lastFetch IS NOT NULL
                    """).fetchall()
                    
                    self.domain_page_counts.clear()
                    
                    for (url,) in result:
                        domain = self._get_domain(url)
                        if domain:
                            self.domain_page_counts[domain] = self.domain_page_counts.get(domain, 0) + 1
                    
                    print(f"✅ Initialized domain counts: {len(self.domain_page_counts)} domains")
                    if self.domain_page_counts:
                        # Show top domains
                        top_domains = sorted(self.domain_page_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                        print(f"   Top domains: {dict(top_domains)}")
                        
            except Exception as e:
                print(f"Warning: Could not initialize domain counts: {e}")
                self.domain_page_counts = {}
    
    def get_domain_page_count(self, domain: str) -> int:
        """Get the number of pages crawled for a domain (thread-safe)."""
        with self._domain_lock:
            return self.domain_page_counts.get(domain, 0)
    
    def update_domain_page_count(self, url: str):
        """Update domain page count when a URL is successfully crawled (thread-safe)."""
        domain = self._get_domain(url)
        if domain:
            with self._domain_lock:
                self.domain_page_counts[domain] = self.domain_page_counts.get(domain, 0) + 1
                # Optional: Log when reaching milestones
                count = self.domain_page_counts[domain]
                if count in [50, 100, 200, 500]:
                    print(f"📊 Domain {domain}: {count} pages crawled")
    
    def get_domain_statistics(self) -> Dict[str, int]:
        """Get current domain page counts (thread-safe)."""
        with self._domain_lock:
            return dict(self.domain_page_counts)
    
    def _get_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    def _get_domain_delay(self, domain: str) -> float:
        """Get the delay for a domain."""
        if domain not in self.domain_delays:
            # Default delay or fetch from robots.txt
            self.domain_delays[domain] = 0.1  # Reduced from 1.0 to 0.1 seconds
        
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