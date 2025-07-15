import re
from bs4 import BeautifulSoup, Comment
from typing import Tuple, Optional, Dict, Any


def parse_html_content(crawler_response: Dict[str, Any]) -> Tuple[str, str]:
    """
    Parse HTML content from a web crawler response and extract clean text content and title.
    
    Args:
        crawler_response: Dictionary containing:
            - "text": HTML content as string
            - "url": URL of the page
            - "code": HTTP status code
            - "contentType": Content-Type header
            - "location": Location header (for redirects)
            - "retry": Retry-Value header
            - "responded": Boolean indicating if request succeeded
            - "robot": robots.txt content (optional)
    
    Returns:
        Tuple[str, str]: (cleaned_content, title)
            - cleaned_content: Main content text without HTML tags, navigation, headers, footers
            - title: Page title as string
    """
    
    def _remove_unwanted_elements(soup: BeautifulSoup) -> None:
        """Remove elements that typically don't contain main content."""
        # Define selectors for elements to remove
        unwanted_selectors = [
            # Navigation elements
            'nav', 'navbar', '[role="navigation"]', '.nav', '.navbar', '.navigation',
            '.menu', '.main-menu', '.primary-menu', '.secondary-menu',
            
            # Headers and footers
            'header', 'footer', '.header', '.footer', '.site-header', '.site-footer',
            '.page-header', '.page-footer',
            
            # Sidebars and aside content
            'aside', '.sidebar', '.side-bar', '.widget', '.widgets',
            
            # Ads and promotional content
            '.ad', '.ads', '.advertisement', '.promo', '.promotion', '.sponsored',
            '.google-ad', '.adsense', '[class*="ad-"]', '[id*="ad-"]',
            
            # Social media and sharing
            '.social', '.share', '.sharing', '.social-media', '.social-links',
            '.follow', '.subscribe',
            
            # Comments and user interactions
            '.comments', '.comment', '.comment-section', '.disqus',
            '.facebook-comments', '.livefyre',
            
            # Breadcrumbs and pagination
            '.breadcrumb', '.breadcrumbs', '.pagination', '.pager',
            
            # Metadata and technical elements
            '.meta', '.metadata', '.byline', '.author-info', '.post-meta',
            '.entry-meta', '.article-meta',
            
            # Related content that might be noisy
            '.related', '.related-posts', '.similar', '.more-stories',
            '.recommended', '.popular', '.trending',
            
            # Common CMS and theme elements
            '.wp-caption', '.wp-caption-text', '.gallery-caption',
            '.screen-reader-text', '.sr-only', '.visually-hidden',
            
            # Newsletter and subscription forms
            '.newsletter', '.subscription', '.signup', '.email-signup',
            
            # Cookie notices and popups
            '.cookie', '.popup', '.modal', '.overlay', '.notice',
            
            # Skip links and accessibility elements that aren't content
            '.skip-link', '.skip-to-content'
        ]
        
        # Remove elements by selector
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Remove specific tags that rarely contain main content
        unwanted_tags = [
            'script', 'style', 'noscript', 'iframe', 'embed', 'object',
            'applet', 'canvas', 'svg', 'math', 'form', 'input', 'button',
            'select', 'textarea', 'label', 'fieldset', 'legend'
        ]
        
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
    
    def _identify_main_content(soup: BeautifulSoup) -> BeautifulSoup:
        """Identify and extract the main content area of the page."""
        # Try to find main content using semantic HTML5 and common patterns
        main_content_selectors = [
            # HTML5 semantic elements
            'main',
            '[role="main"]',
            'article',
            
            # Common content container patterns
            '.content', '.main-content', '.page-content', '.post-content',
            '.entry-content', '.article-content', '.content-area',
            '.primary-content', '.main-area', '.content-wrapper',
            
            # Blog and CMS specific
            '.post', '.entry', '.article', '.story',
            '.post-body', '.entry-body', '.article-body',
            
            # Generic content containers
            '#content', '#main-content', '#primary', '#main',
            '.container .content', '.wrapper .content'
        ]
        
        # Try each selector in order of preference
        for selector in main_content_selectors:
            elements = soup.select(selector)
            if elements:
                # Return the first (usually most relevant) element
                return elements[0]
        
        # If no main content area found, try to find the largest text container
        # This is a fallback for pages without semantic markup
        text_containers = soup.find_all(['div', 'section', 'article'])
        if text_containers:
            # Score containers by text length
            best_container = max(text_containers, 
                               key=lambda x: len(x.get_text(strip=True)))
            return best_container
        
        # Ultimate fallback - return body
        return soup.find('body') or soup
    
    def _clean_text(text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
        
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove extra newlines but preserve paragraph breaks
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove common unwanted patterns
        unwanted_patterns = [
            r'^\s*-\s*$',  # Lines with just dashes
            r'^\s*\*\s*$',  # Lines with just asterisks
            r'^\s*•\s*$',  # Lines with just bullets
            r'^\s*\|\s*$',  # Lines with just pipes
        ]
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and unwanted patterns
            if not line:
                continue
                
            skip_line = False
            for pattern in unwanted_patterns:
                if re.match(pattern, line):
                    skip_line = True
                    break
            
            if not skip_line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _extract_title(soup: BeautifulSoup) -> str:
        """Extract page title with fallbacks."""
        # Try different title sources in order of preference
        title_selectors = [
            'title',
            'h1',
            '.title',
            '.page-title',
            '.post-title',
            '.entry-title',
            '.article-title',
            '[property="og:title"]',
            '[name="twitter:title"]'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                if selector.startswith('['):
                    # For meta tags, get content attribute
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text(strip=True)
                
                if title:
                    return title
        
        return "Untitled"
    
    def _is_valid_html_content(text: str, content_type: str) -> bool:
        """Check if the content is likely to be HTML."""
        if not text:
            return False
            
        # Check content type
        if content_type and 'text/html' in content_type.lower():
            return True
        
        # Check for HTML markers
        html_markers = ['<html', '<head', '<body', '<title', '<div', '<p', '<h1', '<h2']
        text_lower = text.lower()
        return any(marker in text_lower for marker in html_markers)
    
    try:
        # Validate input
        if not crawler_response or not isinstance(crawler_response, dict):
            return "", "Untitled"
        
        # Check if request was successful
        if not crawler_response.get("responded", False):
            return "", "Untitled"
        
        # Check HTTP status code
        status_code = crawler_response.get("code", 0)
        if status_code < 200 or status_code >= 300:
            return "", "Untitled"
        
        # Get the HTML text
        html_text = crawler_response.get("text", "")
        if not html_text:
            return "", "Untitled"
        
        # Check if content appears to be HTML
        content_type = crawler_response.get("contentType", "")
        if not _is_valid_html_content(html_text, content_type):
            # If it's not HTML, return the text as-is (might be plain text, JSON, etc.)
            return html_text.strip(), "Untitled"
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Extract title before cleaning
        title = _extract_title(soup)
        
        # Remove unwanted elements
        _remove_unwanted_elements(soup)
        
        # Identify main content area
        main_content = _identify_main_content(soup)
        
        # Extract text content
        if main_content:
            # Get text with some structure preserved
            raw_text = main_content.get_text(separator='\n', strip=True)
        else:
            raw_text = soup.get_text(separator='\n', strip=True)
        
        # Clean the extracted text
        cleaned_content = _clean_text(raw_text)
        
        # Final validation
        if not cleaned_content or len(cleaned_content.strip()) < 10:
            # If we got very little content, try a more permissive approach
            fallback_content = soup.get_text(separator=' ', strip=True)
            cleaned_content = _clean_text(fallback_content)
        
        return  cleaned_content,title
        
    except Exception as e:
        # Log error in production, for now return empty results
        print(f"Error parsing HTML: {e}")
        return "", "Untitled"


def parse_html_content_simple(html_text: str) -> Tuple[str, str]:
    """
    Simplified version that takes just the HTML text as input.
    
    Args:
        html_text: Raw HTML content as string
    
    Returns:
        Tuple[str, str]: (cleaned_content, title)
    """
    # Create a minimal crawler response format
    crawler_response = {
        "text": html_text,
        "responded": True,
        "code": 200,
        "contentType": "text/html"
    }
    
    return parse_html_content(crawler_response)


def parse_html_content_fast(crawler_response: Dict[str, Any]) -> Tuple[str, str]:
    """
    Fast version of HTML parsing optimized for parallel processing.
    Trades some content quality for significant speed improvements.
    
    Args:
        crawler_response: Dictionary containing response data
    
    Returns:
        Tuple[str, str]: (cleaned_content, title)
    """
    try:
        # Validate input
        if not crawler_response or not isinstance(crawler_response, dict):
            return "", "Untitled"
        
        # Check if request was successful
        if not crawler_response.get("responded", False):
            return "", "Untitled"
        
        # Check HTTP status code
        status_code = crawler_response.get("code", 0)
        if status_code < 200 or status_code >= 300:
            return "", "Untitled"
        
        # Get the HTML text
        html_text = crawler_response.get("text", "")
        if not html_text:
            return "", "Untitled"
        
        # Quick content type check
        content_type = crawler_response.get("contentType", "")
        if content_type and 'text/html' not in content_type.lower():
            # If it's not HTML, check for basic HTML markers
            html_markers = ['<html', '<head', '<body', '<title', '<div', '<p']
            text_lower = html_text.lower()
            if not any(marker in text_lower for marker in html_markers):
                return html_text.strip(), "Untitled"
        
        # Parse with BeautifulSoup using lxml for speed (fallback to html.parser)
        try:
            soup = BeautifulSoup(html_text, 'lxml')
        except:
            soup = BeautifulSoup(html_text, 'html.parser')
        
        # Extract title quickly
        title = "Untitled"
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)
        
        # Remove only the most common unwanted elements (minimal removal for speed)
        for tag_name in ['script', 'style', 'nav', 'footer', 'header', 'aside']:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Try to find main content area quickly
        main_content = None
        for selector in ['main', 'article', '.content', '#content']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # Extract text content
        if main_content:
            raw_text = main_content.get_text(separator=' ', strip=True)
        else:
            raw_text = soup.get_text(separator=' ', strip=True)
        
        # Basic text cleaning (minimal for speed)
        if raw_text:
            # Replace multiple whitespace with single space
            raw_text = re.sub(r'\s+', ' ', raw_text)
            raw_text = raw_text.strip()
        
        return raw_text, title
        
    except Exception as e:
        # Return empty results on error
        return "", "Untitled"


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


# Example usage and test function
def test_parser():
    """Test the HTML parser with sample data."""
    # Sample crawler response
    sample_response = {
        "url": "https://example.com/article",
        "text": """
        <html>
        <head>
            <title>Sample Article Title</title>
        </head>
        <body>
            <nav>
                <ul>
                    <li><a href="/">Home</a></li>
                    <li><a href="/about">About</a></li>
                </ul>
            </nav>
            <header>
                <h1>Website Header</h1>
            </header>
            <main>
                <article>
                    <h1>Sample Article Title</h1>
                    <p>This is the main content of the article. It contains useful information that should be extracted.</p>
                    <p>Here's another paragraph with more content that's relevant to the topic.</p>
                </article>
                <aside>
                    <div class="ads">Advertisement content</div>
                </aside>
            </main>
            <footer>
                <p>Copyright 2024</p>
            </footer>
        </body>
        </html>
        """,
        "code": 200,
        "contentType": "text/html",
        "location": None,
        "retry": None,
        "responded": True
    }
    
    content, title = parse_html_content(sample_response)
    print(f"Title: {title}")
    print(f"Content: {content}")
    print(f"Content length: {len(content)}")


if __name__ == "__main__":
    test_parser()