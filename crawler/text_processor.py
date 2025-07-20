"""Text processing for the Tübingen crawler."""

from bs4 import BeautifulSoup
import re
import time
import signal
from typing import Optional, Tuple
from langdetect import detect, LangDetectException
from contextlib import contextmanager


class TimeoutError(Exception):
    """Custom timeout exception."""
    pass


@contextmanager
def timeout(seconds):
    """Context manager for timeouts."""
    def timeout_handler(signum, frame):
        raise TimeoutError("Operation timed out")
    
    # Set up the timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Restore the old handler
        signal.signal(signal.SIGALRM, old_handler)
        signal.alarm(0)


class TextProcessor:
    """Handles text extraction and processing from HTML/XML content."""
    
    def __init__(self):
        self.html_parser = "html.parser"
        self.xml_parser = "xml"
        self._language_cache = {}  # Cache for language detection
    
    def extract_text(self, content: str, content_type: str = "") -> str:
        """Extract text from HTML content."""
        try:
            # Detect XML content
            is_xml_hint = (
                "xml" in content_type.lower() or
                content.strip().startswith("<?xml") or
                "<rss" in content or 
                "<feed" in content
            )
            
            # Try XML parser first if XML is detected
            if is_xml_hint:
                soup = BeautifulSoup(content, self.xml_parser)
                if self._is_useful_soup(soup):
                    result = self._clean_text(soup.get_text())
                    return result
            
            # Fallback to HTML parser
            soup = BeautifulSoup(content, self.html_parser)
            result = self._clean_text(soup.get_text())
            return result
            
        except Exception as e:
            return self._clean_text(content)
    
    def extract_text_fast(self, content: str) -> str:
        """Fast text extraction for large pages, skipping expensive operations."""
        try:
            # Use a faster, simpler approach for large content
            # Remove scripts and styles first with regex for speed
            import re
            
            # Remove script and style elements
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove HTML tags
            content = re.sub(r'<[^>]+>', ' ', content)
            
            # Decode HTML entities
            import html
            content = html.unescape(content)
            
            # Clean up whitespace
            result = self._clean_text(content)
            return result
            
        except Exception as e:
            # If fast extraction fails, fallback to simple cleaning
            import re
            # Very basic tag removal
            clean_content = re.sub(r'<[^>]+>', ' ', content)
            return self._clean_text(clean_content)
    
    def _is_useful_soup(self, soup: BeautifulSoup) -> bool:
        """Check if parsed soup contains meaningful structure or text."""
        return soup.find() is not None and len(soup.get_text(strip=True)) > 0
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text by removing extra whitespace and normalizing."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of the text with timeout protection."""
        if not text or len(text.strip()) < 50:
            return None
        sample = text[:1000] # Use only first 1000 characters for efficiency
        
        # Check cache first
        cache_key = hash(sample)
        if cache_key in self._language_cache:
            return self._language_cache[cache_key]
        
        try:
            with timeout(5):  # 5 second timeout
                result = detect(sample)
                self._language_cache[cache_key] = result
                return result
        except (LangDetectException, TimeoutError) as e:
            self._language_cache[cache_key] = None
            return None
    
    def is_english(self, text: str) -> bool:
        """Check if text is in English."""
        language = self.detect_language(text)
        result = language == 'en'
        return result
    
    def extract_title(self, content: str) -> Optional[str]:
        """Extract title from HTML content using fast regex method."""
        try:
            # Use regex instead of BeautifulSoup for much better performance
            match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            if match:
                title_text = match.group(1)
                # Decode HTML entities
                import html
                title_text = html.unescape(title_text)
                # Clean the title text
                title_text = self._clean_text(title_text)
                # Return None for empty or whitespace-only titles
                return title_text if title_text else None
        except Exception:
            pass
        return None
    
    def extract_meta_description(self, content: str) -> Optional[str]:
        """Extract meta description from HTML content using fast regex method."""
        try:
            # Use regex instead of BeautifulSoup for better performance
            # Look for meta description tag with name="description"
            pattern = r'<meta[^>]*name\s*=\s*["\']description["\'][^>]*content\s*=\s*["\']([^"\']*)["\'][^>]*>'
            match = re.search(pattern, content, re.IGNORECASE)
            
            if not match:
                # Try alternative pattern (content before name)
                pattern = r'<meta[^>]*content\s*=\s*["\']([^"\']*)["\'][^>]*name\s*=\s*["\']description["\'][^>]*>'
                match = re.search(pattern, content, re.IGNORECASE)
            
            if match:
                description = match.group(1)
                description = self._clean_text(description)
                return description if description else None
        except Exception:
            pass
        return None
    
    def extract_headings(self, content: str) -> list:
        """Extract headings (h1-h6) from HTML content."""
        headings = []
        try:
            soup = BeautifulSoup(content, self.html_parser) # Rarely used
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = self._clean_text(heading.get_text())
                if text:
                    headings.append({
                        'level': heading.name,
                        'text': text
                    })
        except Exception:
            pass
        return headings
    
    def get_text_statistics(self, text: str) -> dict:
        """Get basic statistics about the text."""
        if not text:
            return {
                'length': 0,
                'word_count': 0,
                'sentence_count': 0,
                'paragraph_count': 0
            }
        
        # Word count
        words = text.split()
        word_count = len(words)
        
        # Sentence count (approximate)
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        # Paragraph count (approximate)
        paragraphs = text.split('\n\n')
        paragraph_count = len([p for p in paragraphs if p.strip()])
        
        return {
            'length': len(text),
            'word_count': word_count,
            'sentence_count': sentence_count,
            'paragraph_count': paragraph_count
        }
    
    def get_content_quality_score(self, text: str) -> float:
        """Calculate a quality score for the content."""
        if not text:
            return -2        
        stats = self.get_text_statistics(text)
        score = 0.0
        
        # Length score (optimal around 1000-5000 characters)
        length = stats['length']
        if 1000 <= length <= 5000:
            score += 0.05
        elif 500 <= length < 1000 or 5000 < length <= 10000:
            score += 0.02
        elif 200 <= length < 500:
            score += 0.01
        
        # Word count score
        word_count = stats['word_count']
        if 100 <= word_count <= 1000:
            score += 0.02
        elif 50 <= word_count < 100:
            score += 0.01
        
        # Sentence structure score
        if stats['sentence_count'] > 0:
            avg_words_per_sentence = word_count / stats['sentence_count']
            if 10 <= avg_words_per_sentence <= 25:
                score += 0.02
            elif 5 <= avg_words_per_sentence < 10:
                score += 0.01
        
        
        return score