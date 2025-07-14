"""HTTP client for the Tübingen crawler."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import time
import random
import re

from .config import CrawlerConfig

# Try to import cloudscraper for enhanced Cloudflare protection
import cloudscraper
CLOUDSCRAPER_AVAILABLE = True

# Check for brotli compression support
import brotli
BROTLI_AVAILABLE = True


class DeviceVerificationHandler:
    """Handles device verification challenges."""
    
    def __init__(self):
        self.verification_patterns = [
            # Common device verification indicators
            r"device.?verification",
            r"please.?verify.?you.?are.?human",
            r"robot.?check",
            r"captcha",
            r"cloudflare",
            r"ddos.?protection",
            r"access.?denied",
            r"blocked",
            r"suspicious.?activity",
            r"rate.?limit",
            r"too.?many.?requests",
            r"javascript.?required",
            r"enable.?javascript",
            r"jschl_vc",  # Cloudflare JavaScript challenge
            r"checking.?your.?browser"
        ]
        
        self.verification_status_codes = [403, 429, 503, 401, 406, 408, 409]
        
        # JavaScript challenge patterns
        self.js_challenge_patterns = [
            r"jschl_vc",
            r"jschl_answer",
            r"challenge-form",
            r"var\s+a\s*=\s*function\s*\(",
            r"setTimeout\s*\(\s*function\s*\(",
            r"\.challenge-form"
        ]
    
    def is_device_verification_response(self, response: requests.Response) -> bool:
        """Check if response indicates device verification challenge."""
        # Check status code
        if response.status_code in self.verification_status_codes:
            return True
            
        # Check response content
        content_lower = response.text.lower()
        for pattern in self.verification_patterns:
            if re.search(pattern, content_lower):
                return True
                
        # Check headers
        headers = response.headers
        if 'cf-ray' in headers or 'cf-request-id' in headers:
            # Cloudflare protection
            if 'checking your browser' in content_lower or 'ddos protection' in content_lower:
                return True
                
        return False
    
    def get_verification_type(self, response: requests.Response) -> str:
        """Identify the type of verification challenge."""
        content_lower = response.text.lower()
        
        if 'cloudflare' in content_lower or 'cf-ray' in response.headers:
            return 'cloudflare'
        elif 'captcha' in content_lower:
            return 'captcha'
        elif response.status_code == 429:
            return 'rate_limit'
        elif 'robot' in content_lower or 'bot' in content_lower:
            return 'bot_detection'
        elif any(re.search(pattern, content_lower) for pattern in self.js_challenge_patterns):
            return 'javascript_challenge'
        else:
            return 'unknown'
    
    def extract_javascript_challenge(self, response: requests.Response) -> Optional[Dict[str, Any]]:
        """Extract JavaScript challenge parameters from response."""
        content = response.text
        
        # Look for challenge form
        import re
        form_match = re.search(r'<form[^>]*action="([^"]*)"[^>]*method="([^"]*)"', content, re.IGNORECASE)
        if not form_match:
            return None
            
        action = form_match.group(1)
        method = form_match.group(2)
        
        # Extract input fields
        inputs = {}
        input_matches = re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"', content, re.IGNORECASE)
        for name, value in input_matches:
            inputs[name] = value
            
        return {
            'action': action,
            'method': method,
            'inputs': inputs
        }


class HttpClient:
    """HTTP client with retry logic and proper error handling."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.session = requests.Session()
        self.verification_handler = DeviceVerificationHandler()
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        
        # Proxy configuration
        self.proxy_config = None
        if config.use_proxy and config.proxy_url:
            self.proxy_config = {
                'http': config.proxy_url,
                'https': config.proxy_url
            }
            print(f"Using proxy: {config.proxy_url}")
        
        # Session persistence
        self.domain_sessions = {}  # Domain-specific sessions
        self.failed_domains = set()  # Track domains that consistently fail verification
        
        # Print compression support status
        if not BROTLI_AVAILABLE:
            print("Warning: brotli library not available. Brotli compression may cause issues.")
            print("Install with: pip install brotli")
        
        # Initialize cloudscraper if available and enabled
        self.scraper = None
        if CLOUDSCRAPER_AVAILABLE and config.use_cloudscraper_fallback:
            try:
                self.scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': config.cloudscraper_browser,
                        'platform': config.cloudscraper_platform,
                        'desktop': True
                    },
                    delay=config.cloudscraper_delay,
                    debug=False
                )
                
                # Configure cloudscraper headers
                self.scraper.headers.update({
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })
                
                # Configure proxy for cloudscraper if enabled
                if self.proxy_config:
                    self.scraper.proxies.update(self.proxy_config)
                
                print(f"Cloudscraper initialized successfully")
            except Exception as e:
                print(f"Warning: Could not initialize cloudscraper: {e}")
                self.scraper = None
        elif not CLOUDSCRAPER_AVAILABLE and config.use_cloudscraper_fallback:
            print("Warning: cloudscraper not available. Install with: pip install cloudscraper")
        
        # Verification statistics
        self.verification_stats = {
            'total_challenges': 0,
            'successful_bypasses': 0,
            'failed_bypasses': 0,
            'cloudscraper_successes': 0,
            'cloudscraper_failures': 0,
            'brotli_issues': 0,
            'by_type': {
                'rate_limit': {'attempts': 0, 'successes': 0},
                'cloudflare': {'attempts': 0, 'successes': 0},
                'bot_detection': {'attempts': 0, 'successes': 0},
                'javascript_challenge': {'attempts': 0, 'successes': 0},
                'captcha': {'attempts': 0, 'successes': 0},
                'unknown': {'attempts': 0, 'successes': 0}
            }
        }
        
        self._setup_session()
    
    def _check_brotli_decompression(self, response: requests.Response) -> bool:
        """Check if response was properly decompressed from brotli."""
        content_encoding = response.headers.get('Content-Encoding', '').lower()
        
        if 'br' in content_encoding or content_encoding == 'br':
            # Check if content looks like binary (not properly decompressed)
            try:
                # Try to detect if we have binary content instead of text
                text_content = response.text
                if len(text_content) > 0:
                    # Check if it starts with common HTML/text patterns
                    if (text_content.strip().startswith('<') or 
                        text_content.strip().startswith('<!DOCTYPE') or
                        'html' in text_content[:100].lower()):
                        return True
                    else:
                        # Might be improperly decompressed binary
                        print(f"Warning: Brotli decompression may have failed for response")
                        self.verification_stats['brotli_issues'] += 1
                        return False
            except UnicodeDecodeError:
                print(f"Warning: Unicode decode error - possible brotli decompression issue")
                self.verification_stats['brotli_issues'] += 1
                return False
        
        return True
    
    def _handle_brotli_fallback(self, url: str) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Handle brotli decompression issues by requesting without brotli."""
        print(f"  → Trying request without brotli compression for {url}")
        
        try:
            # Create headers without brotli compression
            headers = self._get_realistic_headers()
            headers['Accept-Encoding'] = 'gzip, deflate'  # Remove 'br'
            
            session = self._get_domain_session(url)
            response = session.get(url, headers=headers, timeout=self.config.timeout)
            
            if response.status_code == 200:
                return response, None
            else:
                return None, f"HTTP {response.status_code}: Non-brotli request failed"
                
        except Exception as e:
            return None, f"Non-brotli fallback error: {str(e)}"
    
    def get_verification_stats(self) -> Dict[str, Any]:
        """Get statistics about device verification handling."""
        return self.verification_stats.copy()

    def _update_verification_stats(self, verification_type: str, success: bool):
        """Update verification statistics."""
        self.verification_stats['total_challenges'] += 1
        
        if success:
            self.verification_stats['successful_bypasses'] += 1
        else:
            self.verification_stats['failed_bypasses'] += 1
            
        if verification_type in self.verification_stats['by_type']:
            self.verification_stats['by_type'][verification_type]['attempts'] += 1
            if success:
                self.verification_stats['by_type'][verification_type]['successes'] += 1
    
    def _retry_with_backoff(self, url: str, max_retries: Optional[int] = None) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Retry request with exponential backoff."""
        if max_retries is None:
            max_retries = self.config.max_verification_retries
            
        for attempt in range(max_retries):
            try:
                # Exponential backoff
                wait_time = (2 ** attempt) * self.config.verification_retry_delay
                time.sleep(wait_time)
                
                # Use different session and headers for each attempt
                session = self._get_domain_session(url)
                headers = self._get_realistic_headers()
                
                response = session.get(url, headers=headers, timeout=self.config.timeout)
                
                # Check if verification is still present
                if not self.verification_handler.is_device_verification_response(response):
                    return response, None
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    return None, f"Max retries exceeded: {str(e)}"
                    
        return None, f"Failed after {max_retries} attempts"
    
    def _setup_session(self):
        """Setup the HTTP session with retry strategy and proxy configuration."""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Configure proxy if enabled
        if self.proxy_config:
            self.session.proxies.update(self.proxy_config)
        
        # Set headers
        if self.config.headers:
            self.session.headers.update(self.config.headers)
    
    def _get_realistic_headers(self) -> Dict[str, str]:
        """Get realistic browser headers to avoid detection."""
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "no-cache",
            "DNT": "1"
        }
        
        # Remove brotli if not available
        if not BROTLI_AVAILABLE:
            headers["Accept-Encoding"] = "gzip, deflate"
        
        return headers
    
    def _get_domain_session(self, url: str) -> requests.Session:
        """Get or create a domain-specific session."""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            
            if domain not in self.domain_sessions:
                session = requests.Session()
                
                # Set up the session similar to main session
                retry_strategy = Retry(
                    total=2,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET", "HEAD"]
                )
                
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
                # Configure proxy if enabled
                if self.proxy_config:
                    session.proxies.update(self.proxy_config)
                
                # Add cookies from main session
                session.cookies.update(self.session.cookies)
                
                self.domain_sessions[domain] = session
                
            return self.domain_sessions[domain]
        except Exception:
            return self.session
    
    def _simulate_human_behavior(self, url: str) -> None:
        """Simulate human browsing behavior."""
        if not self.config.simulate_human_behavior:
            return
            
        # Random delay between requests
        time.sleep(random.uniform(0.5, 2.0))
        
        # Occasionally visit the homepage first
        if random.random() < 0.3:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                homepage_url = f"{parsed.scheme}://{parsed.netloc}/"
                
                # Quick visit to homepage
                session = self._get_domain_session(url)
                session.get(homepage_url, timeout=5, headers=self._get_realistic_headers())
                time.sleep(random.uniform(0.5, 1.5))
            except Exception:
                pass  # Ignore errors in human behavior simulation
    
    def _try_cloudscraper_fallback(self, url: str) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Try to download URL using cloudscraper as fallback for Cloudflare protection."""
        if not self.scraper:
            return None, "Cloudscraper not available"
        
        try:
            print(f"  → Attempting cloudscraper fallback for {url}")
            
            # Random delay to appear more human-like
            time.sleep(random.uniform(1, self.config.cloudscraper_delay))
            
            # Use cloudscraper to get the page
            response = self.scraper.get(url, timeout=self.config.cloudscraper_timeout)
            
            if response.status_code == 200:
                # Create a mock response object compatible with requests.Response
                class MockResponse:
                    def __init__(self, scraper_response):
                        self.status_code = scraper_response.status_code
                        self.text = scraper_response.text
                        self.content = scraper_response.content
                        self.headers = scraper_response.headers
                        self.url = scraper_response.url
                        self.encoding = scraper_response.encoding
                        self.reason = getattr(scraper_response, 'reason', 'OK')
                        self.cookies = scraper_response.cookies
                        self.elapsed = getattr(scraper_response, 'elapsed', None)
                        self.history = getattr(scraper_response, 'history', [])
                        self.links = getattr(scraper_response, 'links', {})
                        self.next = getattr(scraper_response, 'next', None)
                        self.ok = scraper_response.status_code < 400
                        self.is_redirect = 300 <= scraper_response.status_code < 400
                        self.is_permanent_redirect = scraper_response.status_code in (301, 308)
                        self.request = getattr(scraper_response, 'request', None)
                        self._scraper_response = scraper_response  # Store reference for methods
                        
                    def json(self, **kwargs):
                        return self._scraper_response.json(**kwargs) if hasattr(self._scraper_response, 'json') else None
                        
                    def raise_for_status(self):
                        if self.status_code >= 400:
                            raise requests.exceptions.HTTPError(f"{self.status_code} Client Error")
                
                mock_response = MockResponse(response)
                self.verification_stats['cloudscraper_successes'] += 1
                print(f"  ✓ Cloudscraper fallback successful for {url}")
                return mock_response, None  # type: ignore
            else:
                self.verification_stats['cloudscraper_failures'] += 1
                return None, f"HTTP {response.status_code}: {response.reason}"
                
        except Exception as e:
            self.verification_stats['cloudscraper_failures'] += 1
            return None, f"Cloudscraper error: {str(e)}"

    def _handle_device_verification(self, url: str, response: requests.Response) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Handle device verification challenges."""
        if not self.config.handle_device_verification:
            return None, "Device verification handling disabled"
            
        verification_type = self.verification_handler.get_verification_type(response)
        print(f"Handling {verification_type} verification for {url}")
        
        success = False
        result = None, None
        
        try:
            if verification_type == 'rate_limit':
                # Handle rate limiting
                if self.config.respect_rate_limits:
                    retry_after = response.headers.get('Retry-After', str(self.config.default_rate_limit_wait))
                    wait_time = int(retry_after) if retry_after.isdigit() else self.config.default_rate_limit_wait
                    print(f"Rate limited. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    time.sleep(self.config.verification_retry_delay)
                
                # Retry with different user agent
                headers = self._get_realistic_headers()
                try:
                    session = self._get_domain_session(url)
                    new_response = session.get(url, headers=headers, timeout=self.config.timeout)
                    if not self.verification_handler.is_device_verification_response(new_response):
                        result = new_response, None
                        success = True
                    else:
                        result = None, "Rate limit bypass failed"
                except Exception as e:
                    result = None, f"Retry after rate limit failed: {str(e)}"
                    
            elif verification_type == 'cloudflare':
                # Handle Cloudflare protection
                print(f"Cloudflare protection detected for {url}")
                
                # Wait a bit and retry with different headers
                time.sleep(random.uniform(2, 5))
                headers = self._get_realistic_headers()
                headers.update({
                    "Referer": url,
                    "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
                })
                
                try:
                    session = self._get_domain_session(url)
                    new_response = session.get(url, headers=headers, timeout=self.config.timeout * 2)
                    if not self.verification_handler.is_device_verification_response(new_response):
                        result = new_response, None
                        success = True
                    else:
                        # Try cloudscraper fallback for Cloudflare
                        result = self._try_cloudscraper_fallback(url)
                        success = result[0] is not None
                        if not success:
                            result = None, "Cloudflare protection could not be bypassed"
                except Exception as e:
                    # Try cloudscraper fallback on exception
                    result = self._try_cloudscraper_fallback(url)
                    success = result[0] is not None
                    if not success:
                        result = None, f"Cloudflare bypass failed: {str(e)}"
                    
            elif verification_type == 'bot_detection':
                # Handle bot detection
                print(f"Bot detection for {url}")
                
                # Wait and retry with more realistic behavior
                time.sleep(random.uniform(1, 3))
                headers = self._get_realistic_headers()
                
                try:
                    session = self._get_domain_session(url)
                    new_response = session.get(url, headers=headers, timeout=self.config.timeout)
                    if not self.verification_handler.is_device_verification_response(new_response):
                        result = new_response, None
                        success = True
                    else:
                        # Try cloudscraper fallback for bot detection
                        result = self._try_cloudscraper_fallback(url)
                        success = result[0] is not None
                        if not success:
                            result = None, "Bot detection bypass failed"
                except Exception as e:
                    # Try cloudscraper fallback on exception
                    result = self._try_cloudscraper_fallback(url)
                    success = result[0] is not None
                    if not success:
                        result = None, f"Bot detection bypass failed: {str(e)}"
                    
            elif verification_type == 'javascript_challenge':
                # Handle JavaScript challenges
                print(f"JavaScript challenge detected for {url}")
                
                # Extract challenge parameters
                challenge_params = self.verification_handler.extract_javascript_challenge(response)
                if not challenge_params:
                    # Try cloudscraper fallback if we can't extract parameters
                    result = self._try_cloudscraper_fallback(url)
                    success = result[0] is not None
                    if not success:
                        result = None, "Could not extract JavaScript challenge parameters"
                else:
                    action = challenge_params['action']
                    method = challenge_params['method']
                    inputs = challenge_params['inputs']
                    
                    # Construct the challenge URL
                    from urllib.parse import urljoin
                    challenge_url = urljoin(url, action)
                    
                    # Wait a bit to simulate JavaScript execution
                    time.sleep(random.uniform(3, 6))
                    
                    # Make the challenge request
                    try:
                        session = self._get_domain_session(url)
                        if method.lower() == 'post':
                            new_response = session.post(challenge_url, data=inputs, timeout=self.config.timeout)
                        else:
                            new_response = session.get(challenge_url, params=inputs, timeout=self.config.timeout)
                        
                        if not self.verification_handler.is_device_verification_response(new_response):
                            result = new_response, None
                            success = True
                        else:
                            # Try cloudscraper fallback if challenge failed
                            result = self._try_cloudscraper_fallback(url)
                            success = result[0] is not None
                            if not success:
                                result = None, "JavaScript challenge bypass failed"
                    except Exception as e:
                        # Try cloudscraper fallback on exception
                        result = self._try_cloudscraper_fallback(url)
                        success = result[0] is not None
                        if not success:
                            result = None, f"JavaScript challenge bypass failed: {str(e)}"
                        
            elif verification_type == 'captcha':
                # CAPTCHA - try cloudscraper fallback first
                print(f"CAPTCHA detected for {url}")
                result = self._try_cloudscraper_fallback(url)
                success = result[0] is not None
                if not success:
                    result = None, "CAPTCHA detected - cannot be automatically bypassed"
                
            else:
                # Unknown verification type - try cloudscraper fallback then generic retry
                result = self._try_cloudscraper_fallback(url)
                success = result[0] is not None
                if not success:
                    result = self._retry_with_backoff(url, 2)
                    success = result[0] is not None
                
        finally:
            # Update statistics
            self._update_verification_stats(verification_type, success)
            
        return result

    def get(self, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[str]]:
        """
        Make a GET request to the given URL.
        
        Returns:
            Tuple of (response, error_message)
        """
        try:
            # Check if domain has consistently failed verification
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            if domain in self.failed_domains:
                return None, "Domain consistently fails device verification"
            
            # Simulate human behavior
            self._simulate_human_behavior(url)
            
            # Get domain-specific session
            session = self._get_domain_session(url)
            
            # Set default parameters
            params = {
                'timeout': self.config.timeout,
                'allow_redirects': self.config.allow_redirects,
                **kwargs
            }
            
            # Add realistic headers
            if 'headers' not in params:
                params['headers'] = self._get_realistic_headers()
            
            # Make the request
            response = session.get(url, **params)
            
            # Check for device verification
            if self.verification_handler.is_device_verification_response(response):
                print(f"Device verification detected for {url}")
                
                # Try to handle verification
                result = self._handle_device_verification(url, response)
                
                # If still failing, track the domain
                if result[0] is None:
                    self.failed_domains.add(domain)
                    print(f"Added {domain} to failed domains list")
                
                return result
            
            # Check for brotli decompression issues
            if response.status_code == 200 and not self._check_brotli_decompression(response):
                print(f"Brotli decompression issue detected for {url}")
                
                # Try brotli fallback (request without brotli)
                fallback_result = self._handle_brotli_fallback(url)
                if fallback_result[0] is not None:
                    print(f"  ✓ Brotli fallback successful")
                    return fallback_result
                
                # If brotli fallback fails, try cloudscraper as last resort
                if self.scraper:
                    print(f"  → Trying cloudscraper as last resort for brotli issue")
                    cloudscraper_result = self._try_cloudscraper_fallback(url)
                    if cloudscraper_result[0] is not None:
                        return cloudscraper_result
                
                # If all else fails, return the original response with a warning
                print(f"  ⚠ Using original response despite brotli issues")
                return response, "Warning: possible brotli decompression issue"
            
            return response, None
            
        except requests.exceptions.Timeout:
            return None, "Request timeout"
        except requests.exceptions.ConnectionError:
            return None, "Connection error"
        except requests.exceptions.RequestException as e:
            return None, f"Request error: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"

    def head(self, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[str]]:
        """
        Make a HEAD request to the given URL.
        
        Returns:
            Tuple of (response, error_message)
        """
        try:
            params = {
                'timeout': self.config.timeout,
                'allow_redirects': self.config.allow_redirects,
                **kwargs
            }
            
            # Add realistic headers
            if 'headers' not in params:
                params['headers'] = self._get_realistic_headers()
            
            response = self.session.head(url, **params)
            return response, None
            
        except requests.exceptions.Timeout:
            return None, "Request timeout"
        except requests.exceptions.ConnectionError:
            return None, "Connection error"
        except requests.exceptions.RequestException as e:
            return None, f"Request error: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
    
    def is_redirect(self, response: requests.Response) -> bool:
        """Check if the response is a redirect."""
        return 300 <= response.status_code < 400
    
    def is_success(self, response: requests.Response) -> bool:
        """Check if the response is successful."""
        return 200 <= response.status_code < 300
    
    def is_client_error(self, response: requests.Response) -> bool:
        """Check if the response is a client error."""
        return 400 <= response.status_code < 500
    
    def is_server_error(self, response: requests.Response) -> bool:
        """Check if the response is a server error."""
        return 500 <= response.status_code < 600
    
    def get_content_type(self, response: requests.Response) -> Optional[str]:
        """Get the content type from the response."""
        return response.headers.get('Content-Type', '').lower()
    
    def get_last_modified(self, response: requests.Response) -> Optional[datetime]:
        """Get the last modified date from the response."""
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
            try:
                return datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
            except ValueError:
                return None
        return None
    
    def get_etag(self, response: requests.Response) -> Optional[str]:
        """Get the ETag from the response."""
        return response.headers.get('ETag')
    
    def is_html_content(self, response: requests.Response) -> bool:
        """Check if the response contains HTML content."""
        content_type = self.get_content_type(response)
        return bool(content_type and ('text/html' in content_type or 'application/xhtml' in content_type))
    
    def is_xml_content(self, response: requests.Response) -> bool:
        """Check if the response contains XML content."""
        content_type = self.get_content_type(response)
        return bool(content_type and ('application/xml' in content_type or 'text/xml' in content_type))
    
    def close(self):
        """Close all sessions and clean up resources."""
        self.session.close()
        
        # Close domain-specific sessions
        for session in self.domain_sessions.values():
            session.close()
        self.domain_sessions.clear()
        
        # Close cloudscraper session if it exists
        if self.scraper:
            try:
                self.scraper.close()
            except Exception as e:
                print(f"Warning: Error closing cloudscraper session: {e}")
        
        self.failed_domains.clear()

    def get_fast(self, url: str, timeout: float = 2.0) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Fast HTTP GET with shorter timeout for performance testing."""
        try:
            original_timeout = self.config.timeout
            self.config.timeout = int(timeout)
            
            try:
                return self.get(url)
            finally:
                self.config.timeout = original_timeout
                
        except Exception as e:
            return None, str(e)


class ResponseHandler:
    """Handler for processing HTTP responses."""
    
    @staticmethod
    def handle_redirect(response: requests.Response) -> Optional[str]:
        """Handle redirect responses and return the redirect URL."""
        if 300 <= response.status_code < 400:
            return response.headers.get('Location')
        return None
    
    @staticmethod
    def should_retry(response: requests.Response) -> bool:
        """Determine if a request should be retried based on status code."""
        # Retry on server errors and rate limiting
        return response.status_code in [429, 500, 502, 503, 504]
    
    @staticmethod
    def get_retry_delay(response: requests.Response) -> int:
        """Get the retry delay from response headers."""
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    return int(retry_after)
                except ValueError:
                    pass
        return 60  # Default delay 