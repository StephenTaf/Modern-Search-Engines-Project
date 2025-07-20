"""HTTP client for crawler. This allows to use proxy."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import time
import random
import re
# To pass Cloudflare protection
import cloudscraper
# Brotli compression support for some pages
import brotli

from .config import CrawlerConfig

class DeviceVerificationHandler:
    """Handles device verification challenges."""
    
    def __init__(self):
        self.verification_patterns = [
            # Patterns that indicate we are faced with verification!
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
        # Codes that indicate that verification is needed
        self.verification_status_codes = [403, 429, 503, 401, 406, 408, 409]
        
        # JS challenge patterns
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
        # By status code
        if response.status_code in self.verification_status_codes:
            return True
        # By content
        content_lower = response.text.lower()
        for pattern in self.verification_patterns:
            if re.search(pattern, content_lower):
                return True
        # Check headers
        headers = response.headers
        if 'cf-ray' in headers or 'cf-request-id' in headers:
            # Indicates Cloudflare protection
            if 'checking your browser' in content_lower or 'ddos protection' in content_lower:
                return True
                
        return False
    
    def get_verification_type(self, response: requests.Response) -> str:
        """Identify the type of verification challenge. This will be used to try to pass with specific tool."""
        content_lower = response.text.lower()
        
        if 'cloudflare' in content_lower or 'cf-ray' in response.headers:
            return 'cloudflare'
        elif 'captcha' in content_lower:
            return 'captcha'
        elif response.status_code == 429:
            return 'rate_limit'
        elif 'robot' in content_lower or 'bot' in content_lower:
            return 'bot_detection'
        else:
            return 'unknown'

class HttpClient:
    """HTTP client to make requests with additional logic of retries and bypassing verification."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.session = requests.Session()
        self.verification_handler = DeviceVerificationHandler()
        self.user_agents = [ # Realistic user-agents to avoid extra verification
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        
        # In case of proxy, here we set it up
        self.proxy_config = None
        if config.use_proxy and config.proxy_url:
            self.proxy_config = {
                'http': config.proxy_url,
                'https': config.proxy_url
            }
            print(f"Using proxy: {config.proxy_url}")
        self.domain_sessions = {}  # Domain-specific sessions
        self.failed_domains = set()  # Track domains that consistently fail verification
        
        # Initialize cloudscraper scrapper for cloudflare protection
        self.scraper = None
        if config.use_cloudscraper_fallback:
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
                
                # Take headers to indicate allowed types and etc.
                self.scraper.headers.update({
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })
                if self.proxy_config:
                    self.scraper.proxies.update(self.proxy_config)
                print(f"Cloudscraper initialized successfully")
            except Exception as e:
                print(f"Could not initialize cloudscraper: {e}")
                self.scraper = None
            else:
                print("[SYSTEM] Something unusial")
        
        # Track statistics of verification bypass
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
        """Check response decompression from brotli. Was a pain to get binary data."""
        content_encoding = response.headers.get('Content-Encoding', '').lower()
        if 'br' in content_encoding or content_encoding == 'br':
            try:
                # Try to detect if we have binary content instead of text!
                text_content = response.text
                if len(text_content) > 0:
                    # Has tags -> HTML
                    if (text_content.strip().startswith('<') or 
                        text_content.strip().startswith('<!DOCTYPE') or
                        'html' in text_content[:100].lower()):
                        return True
                    else:
                        # Improperly decompressed binary!!!
                        print(f"[WARNING] Brotli decompression may have failed for response")
                        self.verification_stats['brotli_issues'] += 1
                        return False
            except UnicodeDecodeError:
                print(f"[WARNING] Unicode decode error - possible brotli decompression issue")
                self.verification_stats['brotli_issues'] += 1
                return False
        
        return True
    
    def _handle_brotli_fallback(self, url: str) -> Tuple[Optional[requests.Response], Optional[str]]:
        print(f"Brotli compression for {url}")
        
        try:
            headers = self._get_realistic_headers()
            headers['Accept-Encoding'] = 'gzip, deflate'  # Remove 'br' to exclude brotli
            
            session = self._get_domain_session(url)
            response = session.get(url, headers=headers, timeout=self.config.timeout)
            
            if response.status_code == 200:
                return response, None
            else:
                return None, f"HTTP {response.status_code}: Non-brotli request failed"
                
        except Exception as e:
            return None, f"[BROTLI] Fallback error: {str(e)}"
    
    def _retry_with_backoff(self, url: str, max_retries: Optional[int] = None) -> Tuple[Optional[requests.Response], Optional[str]]:
        if max_retries is None:
            max_retries = self.config.max_verification_retries
            
        for attempt in range(max_retries):
            try:
                # Exponential backoff
                wait_time = (2 ** attempt) * self.config.verification_retry_delay
                time.sleep(wait_time)
                
                # Use different session and headers for each attempt to bypass wierd headers check
                session = self._get_domain_session(url)
                headers = self._get_realistic_headers()
                
                response = session.get(url, headers=headers, timeout=self.config.timeout)
                # Check if verification is still present -> Can't bypass
                if not self.verification_handler.is_device_verification_response(response):
                    return response, None
            except Exception as e:
                if attempt == max_retries - 1:
                    return None, f"Max retries exceeded: {str(e)}"
                    
        return None, f"Failed after {max_retries} attempts"
    
    def _setup_session(self):
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        if self.proxy_config: # use proxy
            self.session.proxies.update(self.proxy_config)
        if self.config.headers:
            self.session.headers.update(self.config.headers)
    
    def _get_realistic_headers(self) -> Dict[str, str]:
        """Get realistic browser headers to avoid detection."""
        headers = {
            "User-Agent": random.choice(self.user_agents), # different user agent helps to change "identity" somehow
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
        
        return headers
    
    def _get_domain_session(self, url: str) -> requests.Session:
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            
            if domain not in self.domain_sessions:
                session = requests.Session()
                retry_strategy = Retry(
                    total=2,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET", "HEAD"]
                )
                
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                if self.proxy_config:
                    session.proxies.update(self.proxy_config)
                session.cookies.update(self.session.cookies) # keep cookies from main session
                self.domain_sessions[domain] = session
            return self.domain_sessions[domain]
        except Exception:
            return self.session
    
    def _try_cloudscraper_fallback(self, url: str) -> Tuple[Optional[requests.Response], Optional[str]]:
        # If we have cloudflare protection - try to bypass
        if not self.scraper:
            return None, "Cloudscraper not available"
        try:
            print(f"[CLOUDFLARE] Attempting cloudscraper fallback for {url}") # Usually it helps
            
            time.sleep(random.uniform(1, self.config.cloudscraper_delay)) # Pretend to be more human-like
            response = self.scraper.get(url, timeout=self.config.cloudscraper_timeout) # Use cloudscraper to get the page
            if response.status_code == 200:
                class MockResponse: # Translate all headers and attributes
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
                        self._scraper_response = scraper_response
                        
                    def json(self, **kwargs):
                        return self._scraper_response.json(**kwargs) if hasattr(self._scraper_response, 'json') else None
                        
                    def raise_for_status(self):
                        if self.status_code >= 400:
                            raise requests.exceptions.HTTPError(f"{self.status_code} Client Error")
                
                mock_response = MockResponse(response)
                self.verification_stats['cloudscraper_successes'] += 1
                print(f"[CLOUDFLARE] Cloudscraper fallback successful for {url}") # Usually it helps
                return mock_response, None
            else:
                self.verification_stats['cloudscraper_failures'] += 1
                return None, f"HTTP {response.status_code}: {response.reason}"
                
        except Exception as e:
            self.verification_stats['cloudscraper_failures'] += 1
            return None, f"Cloudscraper error: {str(e)}"

    def _handle_device_verification(self, url: str, response: requests.Response) -> Tuple[Optional[requests.Response], Optional[str]]:
        if not self.config.handle_device_verification:
            return None, "Device verification handling disabled"
            
        verification_type = self.verification_handler.get_verification_type(response)
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
                    result = self._try_cloudscraper_fallback(url)
                    success = result[0] is not None
                    if not success:
                        result = None, f"Bot detection bypass failed: {str(e)}"
            elif verification_type == 'captcha':
                # try cloudscraper fallback first
                print(f"CAPTCHA detected for {url}")
                result = self._try_cloudscraper_fallback(url)
                success = result[0] is not None
                if not success:
                    result = None, "CAPTCHA detected - cannot be automatically bypassed"
            else:
                result = self._try_cloudscraper_fallback(url)
                success = result[0] is not None
                if not success:
                    result = self._retry_with_backoff(url, 2)
                    success = result[0] is not None
        finally:
            self._update_verification_stats(verification_type, success)
            
        return result

    def get(self, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[str]]:
        """
        Make a GET request to the given URL.
        
        Returns:
            Tuple of (response, error_message)
        """
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            if domain in self.failed_domains:
                return None, "Domain consistently fails device verification"
            session = self._get_domain_session(url)
            params = {
                'timeout': self.config.timeout,
                'allow_redirects': self.config.allow_redirects,
                **kwargs
            }
            if 'headers' not in params:
                params['headers'] = self._get_realistic_headers()
            response = session.get(url, **params)
            if self.verification_handler.is_device_verification_response(response):
                print(f"Device verification detected for {url}")
                result = self._handle_device_verification(url, response)
                if result[0] is None:
                    self.failed_domains.add(domain)
                    print(f"Added {domain} to failed domains list")
                
                return result
            
            # Brotli decompression issues
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
                print(f"Using original response despite brotli issues")
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
            
        except requests.exceptions.Timeout: # Fine
            return None, "Request timeout"
        except requests.exceptions.ConnectionError: # Fine
            return None, "Connection error"
        except requests.exceptions.RequestException as e: # Fine
            return None, f"Request error: {str(e)}"
        except Exception as e: # Unusual, but ok
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
        
        for session in self.domain_sessions.values(): # Close domain-specific sessions
            session.close()
        self.domain_sessions.clear()
        
        if self.scraper: # Close cloudscraper session if it exists
            try:
                self.scraper.close()
            except Exception as e:
                print(f"Warning: Error closing cloudscraper session: {e}")
        
        self.failed_domains.clear()

class ResponseHandler:
    """Handler for processing HTTP responses."""
    
    @staticmethod
    def handle_redirect(response: requests.Response) -> Optional[str]:
        if 300 <= response.status_code < 400: # This is redirect
            return response.headers.get('Location')
        return None
    
    @staticmethod
    def should_retry(response: requests.Response) -> bool:
        return response.status_code in [429, 500, 502, 503, 504] # Retry on server errors and rate limiting
    
    @staticmethod
    def get_retry_delay(response: requests.Response) -> int:
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    return int(retry_after)
                except ValueError:
                    pass
        return 60