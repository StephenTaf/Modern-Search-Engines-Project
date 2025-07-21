from bs4 import BeautifulSoup, Comment
from typing import Tuple, Optional, Dict, Any
import re

def parse_html_content_optimized(crawler_response: Dict[str, Any]) -> Tuple[str, str]:
    """
    Optimized HTML parsing that uses lxml parser for better speed and 
    reduces the complexity of content extraction while maintaining quality.
    
    Args:
        crawler_response: Dictionary containing response data
    
    Returns:
        Tuple[str, str]: (cleaned_content, title)
    """
    def _remove_unwanted_elements_fast(soup: BeautifulSoup) -> None:
        """Fast removal of unwanted elements - reduced selector list."""
        # Minimal but effective unwanted element removal
        unwanted_selectors = [
            # Core navigation and layout
            'nav', 'header', 'footer', 'aside',
            # Scripts and styles
            'script', 'style', 'noscript',
            # Ads and social
            '.ad', '.ads', '.social', '.share',
            # Comments and metadata
            '.comment', '.meta', '.breadcrumb'
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
    
    def _identify_main_content_fast(soup: BeautifulSoup) -> BeautifulSoup:
        """Fast main content identification."""
        # Priority order for main content
        for selector in ['main', '[role="main"]', 'article', '.content', '#content']:
            element = soup.select_one(selector)
            if element:
                return element
        
        # Fallback to body
        return soup.find('body') or soup
    
    try:
        # Validate input
        if not crawler_response or not isinstance(crawler_response, dict):
            return "", "Untitled"
        
        if not crawler_response.get("responded", False):
            return "", "Untitled"
        
        status_code = crawler_response.get("code", 0)
        if status_code < 200 or status_code >= 300:
            return "", "Untitled"
        
        html_text = crawler_response.get("text", "")
        if not html_text:
            return "", "Untitled"
        
        # Use lxml for faster parsing
        try:
            soup = BeautifulSoup(html_text, 'lxml')
        except:
            # Fallback to html.parser
            soup = BeautifulSoup(html_text, 'html.parser')
        
        # Extract title
        title = "Untitled"
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)
        
        # Fast unwanted element removal
        _remove_unwanted_elements_fast(soup)
        
        # Fast main content identification
        main_content = _identify_main_content_fast(soup)
        
        # Extract text
        if main_content:
            raw_text = main_content.get_text(separator='\n', strip=True)
        else:
            raw_text = soup.get_text(separator='\n', strip=True)
        
        # Basic text cleaning
        if raw_text:
            # Replace multiple whitespace with single space/newlines
            raw_text = re.sub(r'\s+', ' ', raw_text)
            raw_text = re.sub(r' \n ', '\n', raw_text)
            raw_text = raw_text.strip()
        
        return raw_text, title
        
    except Exception as e:
        return "", "Untitled"
