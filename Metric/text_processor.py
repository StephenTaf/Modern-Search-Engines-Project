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
        """Extract clean text from HTML/XML content."""
        if not content or not content.strip():
            return ""
        
        try:
            # Determine if content is XML-like
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
            # If parsing fails, return cleaned raw text
            return self._clean_text(content)
    
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
        
        # Use only first 1000 characters for efficiency
        sample = text[:1000]
        
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
        """Extract title from HTML content."""
        try:
            soup = BeautifulSoup(content, self.html_parser)
            title_tag = soup.find('title')
            if title_tag:
                return self._clean_text(title_tag.get_text())
        except Exception:
            pass
        return None
    
    def extract_meta_description(self, content: str) -> Optional[str]:
        """Extract meta description from HTML content."""
        try:
            soup = BeautifulSoup(content, self.html_parser)
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                try:
                    content_value = meta_desc.get('content')  # type: ignore
                    if content_value and isinstance(content_value, str):
                        return self._clean_text(content_value)
                except (AttributeError, TypeError):
                    pass
        except Exception:
            pass
        return None
    
    def extract_headings(self, content: str) -> list:
        """Extract headings (h1-h6) from HTML content."""
        headings = []
        try:
            soup = BeautifulSoup(content, self.html_parser)
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
    
    def extract_keywords(self, text: str, min_word_length: int = 3) -> list:
        """Extract potential keywords from text."""
        if not text:
            return []
        
        # Simple keyword extraction - can be improved
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        # Filter by length and common stop words
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'been', 'have', 'has', 'had', 'do',
            'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'this', 'that', 'these', 'those', 'a', 'an', 'it', 'its', 'they',
            'their', 'them', 'we', 'our', 'you', 'your', 'i', 'me', 'my'
        }
        
        keywords = []
        for word in words:
            if len(word) >= min_word_length and word not in stop_words:
                keywords.append(word)
        
        # Count frequency and return most common
        from collections import Counter
        word_freq = Counter(keywords)
        return [word for word, count in word_freq.most_common(50)]
    
    def contains_tuebingen_content(self, text: str) -> bool:
        """Check if text contains Tübingen-related content."""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Tübingen keywords
        tuebingen_keywords = [
            'tübingen', 'tuebingen', 'uni-tuebingen', 'university of tübingen',
            'eberhard karls', 'ekut', 'tue', 'cyber valley', 'max planck'
        ]
        
        return any(keyword in text_lower for keyword in tuebingen_keywords)
    
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