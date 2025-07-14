"""Scoring system for the Tübingen crawler."""

import re
import time
import math
from typing import Dict, List, Optional, Tuple
from collections import Counter

from .config import CrawlerConfig
from .text_processor import TextProcessor


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
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.text_processor = TextProcessor()
        self.terms = TuebingenTerms()
        self.utema = UTEMACalculator(config.utema_beta)
        
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
                score += 0.05
                break
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
        elif url_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg')):
            return 0  # Images less valuable for text content
        elif url_lower.endswith(('.mp3', '.mp4', '.wav', '.ogg', '.webm')):
            return 0  # Audio files
        elif url_lower.endswith(('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
            return 0  # Office files
        elif url_lower.endswith(('.zip', '.rar', '.tar', '.gz', '.bz2')):
            return 0  # Archive files
        elif url_lower.endswith(('.css', '.js', '.json')):
            return 0
            
        # Incorporate parent page score if available
        if parent_score is not None:
            # Give a bonus based on parent page quality (weighted at 20% of parent score)
            parent_bonus = parent_score * 0.3
            score += parent_bonus
        
        return max(0.0, min(1.0, score))
    
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
        if not self.text_processor.is_english(text):
            score -= 0.3 # To allow german pages highly relevant to Tübingen
        
        # Quality bonus
        quality_score = self.text_processor.get_content_quality_score(text)
        score += quality_score * 0.2
        
        return max(min(1.0, score), 0.0)
    
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