"""
URL Content Processing Module for Parallel Execution

This module contains functions for processing URL content in parallel to minimize
subprocess overhead. These functions are designed to be stateless and avoid
dependencies on global variables.
"""

import re
import html
from urllib.parse import urljoin
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import warnings

# Import required modules
from html_parser import parse_html_content, parse_html_content_optimized
from scoring import ContentScorer

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# Global instance to avoid recreating ContentScorer and recompiling regex patterns
_content_scorer = None

def get_content_scorer():
    """Get a shared ContentScorer instance to avoid recompilation overhead."""
    global _content_scorer
    if _content_scorer is None:
        _content_scorer = ContentScorer()
    return _content_scorer

# Sitemap patterns to filter out sitemap URLs
SITEMAP_PATTERNS = [
    r"sitemap.*\.xml$",       # sitemap.xml, sitemap-1.xml, sitemap_news.xml
    r"/sitemap/?$",           # /sitemap or /sitemap/
    r"sitemap_index.*\.xml$", # sitemap_index.xml
]


def is_sitemap_url(url: str) -> bool:
    """
    Check if a URL points to a sitemap.
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if URL is a sitemap, False otherwise
    """
    url = url.lower()
    return any(re.search(p, url) for p in SITEMAP_PATTERNS)


def extract_urls_safe(text, base_url, soup=None):
    """
    Safe version of extractUrls that doesn't modify global variables.
    Used in multiprocessing contexts.
    
    Args:
        text: HTML/XML text content
        base_url: Base URL for resolving relative URLs
        soup: Optional pre-parsed BeautifulSoup object for efficiency
        
    Returns:
        list: List of extracted URLs
    """
    if soup is None:
        soup_type = "xml" if "<?xml" in text or "<rss" in text or "<feed" in text else "html.parser"
        try:
            # Try lxml first for speed, fallback to html.parser
            try:
                soup = BeautifulSoup(text, 'lxml')
            except:
                soup = BeautifulSoup(text, soup_type)
        except:
            return []
    
    try:
        urls = set()

        # --- HTML: clickable hrefs ---
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith(("http", "/")):
                urls.add(urljoin(base_url, href))

        # --- XML: link tags and enclosures ---
        for tag in soup.find_all(["link", "enclosure"]):
            url = tag.get("href") or tag.get("url") or tag.string
            if url and url.strip().startswith(("http", "/")):
                try:
                    urls.add(urljoin(base_url, url.strip()))
                except ValueError:
                    # Don't modify global strangeUrls in multiprocessing
                    pass

        # Unescape HTML entities (e.g. &amp;)
        urls = [html.unescape(u) for u in urls]
        # Filter out sitemap URLs
        final_urls = [url for url in urls if not is_sitemap_url(url)]
        return final_urls
    except:
        return []


def process_url_content_parallel(args):
    """
    Optimized parallelizable function that processes URL content without relying on global dictionaries.
    This function handles CPU-intensive tasks like text parsing, URL extraction, and scoring.
    Uses performance optimizations while maintaining HTML parsing quality.
    
    Args:
        args: tuple containing (urlDict, frontierInfo)
        
    Returns:
        dict: Processed content data or None if processing failed
    """
    urlDict, frontierInfo = args
    
    try:
        url = urlDict["url"]
        
        # Early validation - these don't depend on global state
        if not urlDict["responded"]:
            return {"success": False, "url": url, "reason": "no_response"}
            
        # Parse HTML content - use optimized version for better performance
        # but you can switch back to parse_html_content for maximum quality
        textAndTitle = parse_html_content(urlDict)
        if not textAndTitle or len(textAndTitle) < 2:
            return {"success": False, "url": url, "reason": "parse_failed"}
            
        title = textAndTitle[1]
        text = textAndTitle[0]
        
        if not text and not title:
            return {"success": False, "url": url, "reason": "empty_content"}
            
        # Extract URLs from raw text - reuse parsing if possible
        rawText = urlDict.get("text", "")
        outgoing_urls = []
        if rawText:
            # Use fast URL extraction
            outgoing_urls = extract_urls_safe(rawText, url)
        
        # Calculate score - use shared scorer instance to avoid recompiling regex patterns
        incoming_links = frontierInfo.get("incomingLinks", [])
        linking_depth = frontierInfo.get("linkingDepth", 50)
        
        # Use shared scorer instance to avoid recompiling regex patterns
        scorer = get_content_scorer()
        score = scorer.calculate_final_score(
            url=url, 
            text=text, 
            incoming_links=incoming_links, 
            linking_depth=linking_depth
        )
        
        return {
            "success": True,
            "url": url,
            "title": title,
            "text": text,
            "outgoing": outgoing_urls,
            "score": score,
            "incoming": incoming_links,
            "linkingDepth": linking_depth,
            "domainLinkingDepth": frontierInfo.get("domainLinkingDepth", 5)
        }
        
    except Exception as e:
        return {"success": False, "url": urlDict.get("url", "unknown"), "reason": f"exception: {str(e)}"}


def process_url_content_parallel_full_quality(args):
    """
    Full quality version that uses the complete HTML parsing (slower but highest quality).
    Switch the function call in CrawlerHelpers.py to use this if you need maximum quality.
    
    Args:
        args: tuple containing (urlDict, frontierInfo)
        
    Returns:
        dict: Processed content data or None if processing failed
    """
    urlDict, frontierInfo = args
    
    try:
        url = urlDict["url"]
        
        # Early validation
        if not urlDict["responded"]:
            return {"success": False, "url": url, "reason": "no_response"}
            
        # Use full quality HTML parsing
        textAndTitle = parse_html_content(urlDict)
        if not textAndTitle or len(textAndTitle) < 2:
            return {"success": False, "url": url, "reason": "parse_failed"}
            
        title = textAndTitle[1]
        text = textAndTitle[0]
        
        if not text and not title:
            return {"success": False, "url": url, "reason": "empty_content"}
            
        # Extract URLs from raw text
        rawText = urlDict.get("text", "")
        outgoing_urls = []
        if rawText:
            outgoing_urls = extract_urls_safe(rawText, url)
        
        # Calculate score using shared scorer instance
        incoming_links = frontierInfo.get("incomingLinks", [])
        linking_depth = frontierInfo.get("linkingDepth", 50)
        
        scorer = get_content_scorer()
        score = scorer.calculate_final_score(
            url=url, 
            text=text, 
            incoming_links=incoming_links, 
            linking_depth=linking_depth
        )
        
        return {
            "success": True,
            "url": url,
            "title": title,
            "text": text,
            "outgoing": outgoing_urls,
            "score": score,
            "incoming": incoming_links,
            "linkingDepth": linking_depth,
            "domainLinkingDepth": frontierInfo.get("domainLinkingDepth", 5)
        }
        
    except Exception as e:
        return {"success": False, "url": urlDict.get("url", "unknown"), "reason": f"exception: {str(e)}"}
