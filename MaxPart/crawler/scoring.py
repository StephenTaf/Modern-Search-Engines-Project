"""Scoring system for the Tübingen crawler."""

import re
import time
import math
from typing import Dict, List, Optional, Tuple
from collections import Counter
# Removed langdetect import for faster alternative
from bs4 import XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
class UTEMACalculator:
    """Unbiased Time-Exponential Moving Average calculator."""
    
    def __init__(self, beta: float = 0.2):
        self.beta = beta
        self.data: Dict[str, Dict[str, float]] = {}
    
    def calculate(self, field_name: str, value: float) -> float:
        """Calculate UTEMA for a given field and value."""
        current_time = time.time()
        
        if field_name not in self.data:
            self.data[field_name] = {
                'S_last': value,
                'N_last': 1,
                't_last': current_time
            }
            return value
        
        # Get previous values
        S_last = self.data[field_name]['S_last']
        N_last = self.data[field_name]['N_last']
        t_last = self.data[field_name]['t_last']
        
        # Calculate exponential weight
        exp_weight = math.exp(-self.beta * (current_time - t_last))
        
        # Update values
        S = exp_weight * S_last + value
        N = exp_weight * N_last + 1
        
        # Store updated values
        self.data[field_name]['S_last'] = S
        self.data[field_name]['N_last'] = N
        self.data[field_name]['t_last'] = current_time
        
        # Calculate and return average
        return S / N


class TuebingenTerms:
    """Tübingen-specific terms for content scoring."""
    
    TUEBINGEN_PHRASES = [
        "tübingen", "tuebingen", " tüb ", "tübing", "tuebing"
        "eberhard karls", "ekut"
    ]
    
    CITY_TERMS = [
        "baden-württemberg", "baden-wuerttemberg", "neckar valley",
        "neckartal", "swabian", "schwäbisch", "württemberg", "wuerttemberg", "schwabenland",
        "neckarfront", "stiftskirche", "schwäbische", "hirschau", "hohentübingen", "hohentuebingen", 
        "wilhelmstraße", "wilhelmstrasse", "kirchgasse", "hafengasse", "lustnau",
        "tuebus", "tübus"
    ]
    
    UNIVERSITY_TERMS = [
        "university hospital tübingen", "university hospital tuebingen", "ukt", "ukt tübingen",
        "medizinische fakultät tübingen", "faculty of medicine tübingen",
        "tuebingen medical center", "tuebingen medical faculty", "tuebingen neuroscience",
        "tübingen neuroscience", "tuebingen cognitive science", "tuebingen computer science",
        "tuebingen informatics", "tuebingen mathematics", "tuebingen physics",
        "tuebingen chemistry", "tuebingen law faculty", "faculty of law tübingen",
        "wilhelmsstift", "student life tübingen", "studentenleben tübingen",
        "morgenstelle", "brechtbau", "neue aula", "kupferbau", "hörsaalzentrum"
    ]
    
    ACADEMIC_TERMS = [
        "cyber valley", "max planck", "hertie institute", "dzif", "german centre for infection research",
        "max planck institute", "fraunhofer", "helmholtz", "leibniz institute",
        "excellence cluster", "exzellenzcluster", "sonderforschungsbereich"
    ]


class ContentScorer:
    """Scores content based on Tübingen relevance and quality."""
    
    def __init__(self):
        self.terms = TuebingenTerms()
        self.utema = UTEMACalculator(0.5)
        
        # Compile regex patterns for efficiency
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficient matching."""
        self.tuebingen_pattern = self._compile_regex(self.terms.TUEBINGEN_PHRASES)
        self.city_pattern = self._compile_regex(self.terms.CITY_TERMS)
        self.university_pattern = self._compile_regex(self.terms.UNIVERSITY_TERMS)
        self.academic_pattern = self._compile_regex(self.terms.ACADEMIC_TERMS)
    
    def _compile_regex(self, term_list: List[str]) -> re.Pattern:
        """Compile a regex pattern from a list of terms."""
        # Escape special characters and create pattern
        escaped_terms = [re.escape(term) for term in term_list]
        pattern = '|'.join(escaped_terms)
        return re.compile(pattern, re.IGNORECASE)
    
    def calculate_url_score(self, url: str, parent_url: Optional[str] = None, parent_score: Optional[float] = None) -> float:
        """Calculate URL-based score."""
        score = 0.0
        url_lower = url.lower()
        
        # Tübingen-relevant keywords
        tuebingen_keywords = ['tuebingen', 'tübingen', 'uni-tuebingen', 'tue']
        for keyword in tuebingen_keywords:
            if keyword in url_lower:
                score += 0.025
                break
        if 'wg-gesucht' in url_lower:
            score -= 0.04 # downgrade as they have less diversity
        # English content bonus
        if "/en/" in url_lower or url_lower.endswith("/en"):
            score += 0.02
                
        # Penalize deep paths
        path_depth = url.count('/')
        if path_depth > 6:
            score -= 0.05 * (path_depth - 6) # Reduced penalty

        # Data type -- mainfocus on html
        if url_lower.endswith('.pdf'):
            return 0  # PDFs often contain valuable, but not for now
        elif url_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.webp', '.bmp', '.tiff')):
            return 0  # Images less valuable for text content
        elif url_lower.endswith(('.mp3', '.mp4', '.wav', '.ogg', '.webm', '.avi', '.mov', '.wmv', '.flv', '.mkv')):
            return 0  # Audio/Video files
        elif url_lower.endswith(('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
            return 0  # Office files
        elif url_lower.endswith(('.zip', '.rar', '.tar', '.gz', '.bz2', '.7z', '.deb', '.rpm', '.dmg', '.exe', '.msi')):
            return 0  # Archive and executable files
        elif url_lower.endswith(('.css', '.js', '.json', '.map', '.ts', '.scss', '.less', '.woff', '.woff2', '.ttf', '.eot')):
            return 0  # Web assets and fonts
        elif url_lower.endswith(('.xml', '.rss', '.atom', '.sitemap')):
            return 0  # Structured data files
        elif url_lower.endswith(('.txt', '.log', '.md', '.readme')) and any(x in url_lower for x in ['robot', 'sitemap', 'changelog', 'license']):
            return 0  # System/meta files
        
        # Check for API endpoints and admin areas
        if any(pattern in url_lower for pattern in [
            '/api/', '/admin/', '/wp-admin/', '/wp-content/', '/wp-includes/',
            '/ajax/', '/rest/', '/graphql/', '/soap/', '/_api/', '/backend/',
            '/management/', '/dashboard/', '/control-panel/', '/cpanel/'
        ]):
            return 0  # API endpoints and admin interfaces

        
        # Check for shopping/commerce related pages
        # if any(pattern in url_lower for pattern in [
        #     '/cart/', '/checkout/', '/payment/', '/order/', '/shop/',
        #     '/store/', '/buy/', '/purchase/', '/pricing/', '/plans/'
        # ]):
        #     return 0  # E-commerce pages
        # Forum pagination and individual posts
        
        # Additional technical exclusions
        if '.xml' in url_lower or '.css' in url_lower or '.woff' in url_lower or 'wp-json' in url_lower:
            return 0
    
            
        # Incorporate parent page score if available
        if parent_score is not None:
            # Give a bonus based on parent page quality (weighted at 20% of parent score)
            parent_bonus = parent_score * 0.3
            score += parent_bonus
        
        return max(0.0, min(1.0, score))

    def is_english(self, text: str) -> bool:
        """
        Fast heuristic-based English detection instead of expensive langdetect.
        Checks for common English words and patterns.
        """
        if not text or len(text) < 20:
            return False
            
        text_lower = text.lower()
        
        # Common English words that are unlikely to appear in German
        english_indicators = [
            'the', 'and', 'for', 'are', 'with', 'this', 'that', 'have', 'from', 
            'they', 'been', 'have', 'their', 'said', 'each', 'which', 'time',
            'about', 'after', 'first', 'never', 'these', 'think', 'where',
            'being', 'every', 'great', 'might', 'shall', 'still', 'those',
            'under', 'while', 'should', 'never', 'through', 'during', 'before'
        ]
        
        # German indicators (common German words that rarely appear in English)
        german_indicators = [
            'der', 'die', 'das', 'und', 'ist', 'ich', 'sie', 'ein', 'eine',
            'mit', 'auf', 'für', 'von', 'den', 'des', 'dem', 'sich', 'auch',
            'nach', 'bei', 'aus', 'über', 'nur', 'noch', 'wenn', 'wie',
            'wird', 'werden', 'kann', 'könnte', 'sollte', 'müssen', 'haben',
            'dass', 'aber', 'oder', 'dann', 'sehr', 'mehr', 'waren', 'unter'
        ]
        
        # Count indicators
        english_count = sum(1 for word in english_indicators if f' {word} ' in text_lower)
        german_count = sum(1 for word in german_indicators if f' {word} ' in text_lower)
        
        # Simple decision: if we have more English indicators, consider it English
        # If unclear, default to True to avoid excluding potentially relevant content
        if english_count == 0 and german_count == 0:
            # Check for English URL patterns or common English phrases
            english_patterns = ['university', 'research', 'student', 'education', 'science']
            return any(pattern in text_lower for pattern in english_patterns)
        
        return english_count >= german_count
    def calculate_text_score(self, text: str) -> float:
        """Calculate text content score based on Tübingen relevance."""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        score = 0.0
        
        # Count matches for different term categories
        tuebingen_matches = len(self.tuebingen_pattern.findall(text_lower))
        city_matches = len(self.city_pattern.findall(text_lower))
        university_matches = len(self.university_pattern.findall(text_lower))
        academic_matches = len(self.academic_pattern.findall(text_lower))
        
        # Calculate scores based on matches
        text_length = len(text)
        if text_length > 0:
            # Also it's possible to look for density of matches, but it's not necessary
            # at least for now
            score += 0.48 * (tuebingen_matches > 0)
            score += 0.2 * (city_matches > 0)
            score += 0.2 * (university_matches > 0)
            score += 0.15 * (academic_matches > 0)
        
        # Downgrade non-english pages
        if not self.is_english(text):
            score -= 0.3 # To allow german pages highly relevant to Tübingen
        
        # Quality bonus
        quality_score = self.get_content_quality_score(text)
        score += quality_score * 0.2
        
        return max(min(1.0, score), 0.0)
    
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
    
    def calculate_incoming_links_score(self, incoming_links: List[Tuple[str, float]]) -> float:
        """Calculate score based on incoming links."""
        if not incoming_links:
            return 0.0
        
        total_score = 0.0
        for url, link_score in incoming_links:
            if link_score is not None:
                total_score += link_score
        
        # Normalize by number of links
        avg_score = total_score / len(incoming_links)
        more_than_avg = 0
        for url, link_score in incoming_links:
            if link_score is not None and link_score > avg_score:
                more_than_avg += 1
        
        # Add bonus for having many quality incoming links
        link_count_bonus = 0.01 * more_than_avg
        
        return min(1.0, link_count_bonus)
    
    def calculate_final_score(self, url: str, text: Optional[str] = None, 
                            incoming_links: Optional[List[Tuple[str, float]]] = None,
                            linking_depth: int = 0) -> float:
        """Calculate final score for a URL combining all factors."""
        scores = {}

        # URL score (weight: 0.2)
        url_score = self.calculate_url_score(url)
        if url_score == 0:
            return 0.0
        scores['url'] = url_score * 0.2
        
        # Text score (weight: 0.5)
        if text:
            text_score = self.calculate_text_score(text)
            scores['text'] = text_score * 0.5
        else:
            scores['text'] = 0.0
        
        # Incoming links score (weight: 0.2)
        if incoming_links:
            links_score = self.calculate_incoming_links_score(incoming_links)
            scores['links'] = links_score * 0.2
        else:
            scores['links'] = 0.0
        
        # Depth penalty (weight: 0.1)
        if linking_depth > 0:
            depth_penalty = max(0.0, 1.0 - (linking_depth * 0.1))
            scores['depth'] = depth_penalty * 0.07
        else:
            scores['depth'] = 0.07
        
        # Calculate final score
        final_score = sum(scores.values())
        
        # Apply UTEMA smoothing
        domain = self._get_domain(url)
        if domain:
            final_score = self.utema.calculate(domain, final_score)
        
        return min(1.0, max(0.0, final_score))
    
    def _get_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return None
    
    def get_score_breakdown(self, url: str, text: Optional[str] = None, 
                          incoming_links: Optional[List[Tuple[str, float]]] = None,
                          linking_depth: int = 0) -> Dict[str, float]:
        """Get detailed score breakdown for analysis."""
        breakdown = {}
        
        # Individual scores
        breakdown['url_score'] = self.calculate_url_score(url)
        breakdown['text_score'] = self.calculate_text_score(text) if text else 0.0
        breakdown['links_score'] = self.calculate_incoming_links_score(incoming_links) if incoming_links else 0.0
        breakdown['depth_score'] = max(0.0, 1.0 - (linking_depth * 0.1)) if linking_depth > 0 else 1.0
        
        # Weighted scores
        breakdown['url_weighted'] = breakdown['url_score'] * 0.2
        breakdown['text_weighted'] = breakdown['text_score'] * 0.5
        breakdown['links_weighted'] = breakdown['links_score'] * 0.2
        breakdown['depth_weighted'] = breakdown['depth_score'] * 0.1
        
        # Final score
        breakdown['final_score'] = self.calculate_final_score(url, text, incoming_links, linking_depth)
        
        return breakdown 