"""Clean and organized Tübingen crawler package."""

from .config import CrawlerConfig, DEFAULT_SEED_URLS
from .crawler import TuebingenCrawler
from .database import DatabaseManager
from .http_client import HttpClient, ResponseHandler
from .url_manager import UrlManager
from .text_processor import TextProcessor
from .scoring import ContentScorer, UTEMA, TuebingenTerms
from .frontier import FrontierManager, FrontierEntry

__version__ = "1.0.0"
__author__ = "Tübingen NSE Project"

__all__ = [
    'CrawlerConfig',
    'DEFAULT_SEED_URLS',
    'TuebingenCrawler',
    'DatabaseManager',
    'HttpClient',
    'ResponseHandler',
    'UrlManager',
    'TextProcessor',
    'ContentScorer',
    'UTEMA',
    'TuebingenTerms',
    'FrontierManager',
    'FrontierEntry'
]
