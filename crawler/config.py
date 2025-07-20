"""Configuration settings for the Tübingen crawler."""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import pickle

@dataclass
class CrawlerConfig:
    """Configuration settings for the crawler."""
    
    # HTTP Settings
    headers: Optional[Dict[str, str]] = None
    timeout: int = 5
    allow_redirects: bool = False
    
    # Device Verification Settings
    handle_device_verification: bool = True
    max_verification_retries: int = 3
    verification_retry_delay: float = 2.0
    use_session_persistence: bool = True
    
    # Cloudflare Protection Settings
    use_cloudscraper_fallback: bool = True
    cloudscraper_timeout: int = 15
    cloudscraper_delay: float = 2.0
    cloudscraper_browser: str = "chrome"
    cloudscraper_platform: str = "darwin"
    
    # Rate Limiting
    respect_rate_limits: bool = True
    default_rate_limit_wait: int = 60
    
    # Proxy Settings
    use_proxy: bool = False
    proxy_url: Optional[str] = None  # Format: "socks5://user:pass@host:port" or "http://user:pass@host:port"
    proxy_auth: Optional[Dict[str, str]] = None  # Alternative: {"username": "user", "password": "pass"}
    proxy_timeout: int = 30
    
    # Database Settings
    db_path: str = "crawler.db"
    cache_size_threshold: int = 20000
    
    # Crawling Settings
    max_pages_per_batch: int = 100
    delay_between_batches: int = 100
    
    # Multiprocessing Settings
    enable_multiprocessing: bool = False
    max_workers: int = 4
    urls_per_worker_batch: int = 20
    domain_rotation_delay: float = 0.1
    worker_coordination_delay: float = 0.2
    shared_domain_delays: bool = True  # Share domain delays across processes
    
    # Scoring Settings
    utema_beta: float = 1/5
    
    # Output Settings
    csv_export_enabled: bool = True
    csv_filename: str = "crawled_urls.csv"
    
    def __post_init__(self):
        # These headers help to look like real device
        if self.headers is None:
            self.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "DNT": "1"
            }


# Default seed URLs for Tübingen crawling
with open("crawler/seeds.pickle", 'rb') as file:
    DEFAULT_SEED_URLS = pickle.load(file)

# Common Tübingen-related terms for scoring
TUEBINGEN_TERMS = [
    "tübingen", "tuebingen", "university", "eberhard karls",
    "baden württemberg", "neckar", "swabia", "medieval",
    "student", "academic", "research", "campus", "altstadt",
    "old town", "castle", "schönbuch", "württemberg"
]

# Domain patterns to prioritize
PRIORITY_DOMAINS = [
    "uni-tuebingen.de",
    "tuebingen.de",
    "tuebingen.city",
    "tuebingen.mpg.de",
    "tuebingen.ai",
    "cyber-valley.de",
    "my-stuwe.de",
    "dai-tuebingen.de",
    "tuebingenresearchcampus.com",
    "hih-tuebingen.de"
]

# Domains to avoid
EXCLUDE_DOMAINS = [
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "youtube.com",
    "linkedin.com",
    "pinterest.com",
    "reddit.com",
    "whatsapp.com",
    "telegram.org",
    "tiktok.com",
    "snapchat.com",
    "discord.com",
    "twitch.tv",
    "amazon.com",
    "amazon.de",
    "ebay.com",
    "ebay.de",
    "booking.com",
    "expedia.com",
    "tripadvisor.com",
    "airbnb.com",
    "hotels.com",
    "kayak.com",
    "skyscanner.com",
    "momondo.com",
    "priceline.com",
    "orbitz.com",
    "travelocity.com",
    "cheapflights.com",
    "hotwire.com",
    "lastminute.com",
    "opodo.com",
    "gomio.com",
    "omio.com",
    "flixbus.com",
    "trainline.com",
    "bahn.de",
    "deutsche-bahn.com",
    "blablacar.com",
    "uber.com",
    "lyft.com",
    "mytaxi.com",
    "free-now.com",
    "bolt.eu",
    "via.com",
    "gett.com",
    "kapten.com",
    "cabify.com",
    "99.co",
    "grab.com",
    "ola.com",
    "didi.com",
    "careem.com",
    "yandex.com",
    "mail.ru",
    "vk.com",
    "ok.ru",
    "weibo.com",
    "wechat.com",
    "qq.com",
    "baidu.com",
    "sina.com",
    "163.com",
    "126.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "gmail.com",
    "aol.com",
    "icloud.com",
    "protonmail.com",
    "tutanota.com",
    "zoho.com",
    "fastmail.com",
    "yandex.ru",
    "rambler.ru",
    "bk.ru",
    "inbox.ru",
    "list.ru",
    "internet.ru"
]

# Database table definitions
DATABASE_SCHEMA = {
    "urlsDB": """
        CREATE TABLE IF NOT EXISTS urlsDB (
            url TEXT PRIMARY KEY,
            lastFetch TIMESTAMP,
            text TEXT,
            title TEXT,
            tueEngScore REAL,
            linkingDepth INTEGER,
            domainLinkingDepth INTEGER,
            parentUrl TEXT,
            statusCode INTEGER,
            contentType TEXT,
            lastModified TIMESTAMP,
            etag TEXT
        )
    """,
    
    "frontier": """
        CREATE TABLE IF NOT EXISTS frontier (
            url TEXT PRIMARY KEY,
            schedule REAL,
            delay REAL,
            priority REAL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "disallowed": """
        CREATE TABLE IF NOT EXISTS disallowed (
            url TEXT PRIMARY KEY,
            reason TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "errors": """
        CREATE SEQUENCE IF NOT EXISTS errors_id_seq;
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY DEFAULT nextval('errors_id_seq'),
            url TEXT NOT NULL,
            error_type TEXT,
            error_message TEXT,
            status_code INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
} 