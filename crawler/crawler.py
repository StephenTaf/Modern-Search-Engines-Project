"""Main crawler class for the Tübingen crawler."""

import time
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime
import signal
import sys

from .config import CrawlerConfig, DEFAULT_SEED_URLS
from .database import DatabaseManager
from .http_client import HttpClient, ResponseHandler
from .url_manager import UrlManager
from .text_processor import TextProcessor
from .scoring import ContentScorer
from .frontier import FrontierManager
from .multiprocessing_crawler import MultiprocessingCrawler


class TuebingenCrawler:
    """Main crawler class that orchestrates all components."""
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        self.config = config or CrawlerConfig()

        self.db_manager = DatabaseManager(self.config)
        self.http_client = HttpClient(self.config)
        self.url_manager = UrlManager(self.config, self.http_client)
        self.text_processor = TextProcessor()
        self.scorer = ContentScorer(self.config)  # Initialize without frontier_manager first
        self.frontier = FrontierManager(self.config, self.db_manager, self.scorer)
        
        self.scorer.set_frontier_manager(self.frontier)

        self.is_running = False
        self.should_stop = False
        self.input_thread = None
        
        self.stats = {
            'start_time': None,
            'end_time': None,
            'urls_processed': 0,
            'urls_successful': 0,
            'urls_failed': 0,
            'total_runtime': 0
        }
        
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}. Shutting down gracefully...")
            self.should_stop = True
            print("Waiting for current operations to complete...")
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def add_seed_urls(self, urls: List[str]):
        """Add seed URLs to the frontier."""
        print(f"Adding {len(urls)} seed URLs to frontier...")
        
        for url in urls:
            success = self.frontier.add_url(url, linking_depth=0, domain_linking_depth=0)
            if success:
                print(f"Added seed URL: {url}")
            else:
                print(f"Skipped seed URL: {url}")
    
    def crawl_url(self, url: str, entry) -> bool:
        """Crawl a single URL and process its content."""        
        try:
            print(f"Crawling: {url}")
            if not self.url_manager.is_url_allowed_fast(url):
                print(f"URL not allowed by robots.txt: {url}")
                self.frontier.remove_url(url, "robots.txt disallowed")
                return False
            response, error = self.http_client.get(url)
            
            if error:
                print(f"Error crawling {url}: {error}")
                self.db_manager.log_error(url, "http_error", error)
                self.stats['urls_failed'] += 1
                return False
            
            if not response:
                print(f"No response for {url}")
                self.stats['urls_failed'] += 1
                return False
            
            print(f"Got response for {url}: status={response.status_code}")
            if self.http_client.is_redirect(response):
                print(f"Redirect response for {url}")
                redirect_url = ResponseHandler.handle_redirect(response)
                if redirect_url:
                    # Add redirect URL to frontier
                    full_redirect_url = self.url_manager.normalize_url(redirect_url)
                    self.frontier.add_url(
                        full_redirect_url, 
                        parent_url=url,
                        linking_depth=entry.linking_depth,
                        domain_linking_depth=entry.domain_linking_depth
                    )
                    print(f"Following redirect: {url} -> {full_redirect_url}")
                return True
            
            if not self.http_client.is_success(response):
                error_msg = f"HTTP {response.status_code}"
                print(f"Error response for {url}: {error_msg}")
                self.db_manager.log_error(url, "http_status", error_msg, response.status_code)
                self.stats['urls_failed'] += 1
                return False
            
            # Process successful response
            if self.http_client.is_html_content(response) or self.http_client.is_xml_content(response):
                print(f"Processing HTML/XML content for {url}")
                return self._process_html_content(url, response, entry)
            else:
                print(f"Skipping non-HTML content: {url}")
                return True
                
        except Exception as e:
            print(f"Exception crawling {url}: {e}")
            self.db_manager.log_error(url, "exception", str(e))
            self.stats['urls_failed'] += 1
            return False
    
    def _process_html_content(self, url: str, response, entry) -> bool:
        """Process HTML content from a response."""
        try:
            content_type = self.http_client.get_content_type(response) or "text/html"
            content_size = len(response.text)
            
            text_content = self.text_processor.extract_text_fast(response.text)
            
            score = self.scorer.calculate_final_score(
                url=url,
                text=text_content,
                linking_depth=entry.linking_depth
            )
            title = self.text_processor.extract_title(response.text)
            meta_description = self.text_processor.extract_meta_description(response.text)
            self.db_manager.insert_url(
                url=url,
                text=text_content,
                title=title,
                score=score,
                linking_depth=entry.linking_depth,
                domain_linking_depth=entry.domain_linking_depth,
                parent_url=entry.parent_url,
                status_code=response.status_code,
                content_type=content_type,
                last_modified=self.http_client.get_last_modified(response),
                etag=self.http_client.get_etag(response)
            )
            url_extraction_content = response.text
            if content_size > 2*1024 * 1024:  # 2MB cut
                url_extraction_content = response.text[:2*1024 * 1024]
            
            new_urls = self.url_manager.extract_urls_fast(url_extraction_content, url, max_urls=1000)
            visited_urls = self.frontier.visited_urls.union(self.frontier.crawled_urls)
            disallowed_urls = set()
    
            filtered_urls = self.url_manager.filter_urls_fast(
                new_urls, url, visited_urls, disallowed_urls
            )
            
            # Add new URLs to frontier
            for new_url in filtered_urls:
                self.frontier.add_url(
                    new_url,
                    parent_url=url,
                    linking_depth=entry.linking_depth + 1,
                    domain_linking_depth=entry.domain_linking_depth + 1
                )
            
            print(f"Processed {url}: score={score:.3f}, found {len(filtered_urls)} new URLs")
            
            # Update domain page count for successful crawl
            self.frontier.update_domain_page_count(url)
            
            self.stats['urls_successful'] += 1
            return True
            
        except Exception as e:
            print(f"Error processing content for {url}: {e}")
            self.db_manager.log_error(url, "content_processing", str(e))
            self.stats['urls_failed'] += 1
            return False
    
    def _input_handler(self):
        """Handle user input in a separate thread."""
        while self.is_running:
            try:
                user_input = input().strip().lower()
                if user_input in ['q', 'quit', 'exit', 'stop']:
                    print("Stopping crawler...")
                    self.should_stop = True
                    break
                elif user_input in ['s', 'stats', 'statistics']:
                    self._print_statistics()
                elif user_input in ['h', 'help']:
                    self._print_help()
            except (EOFError, KeyboardInterrupt):
                break
    
    def _print_statistics(self):
        """Print current crawling statistics."""
        frontier_stats = self.frontier.get_statistics()
        db_stats = self.db_manager.get_statistics()
        
        print("\n" + "="*50)
        print("CRAWLER STATISTICS")
        print("="*50)
        print(f"URLs processed: {self.stats['urls_processed']}")
        print(f"URLs successful: {self.stats['urls_successful']}")
        print(f"URLs failed: {self.stats['urls_failed']}")
        print(f"Frontier size: {frontier_stats['frontier_size']}")
        print(f"Visited URLs: {frontier_stats['visited_count']}")
        print(f"Crawled URLs: {db_stats['crawled_urls']}")
        print(f"Disallowed URLs: {db_stats['disallowed_urls']}")
        print(f"Errors: {db_stats['errors']}")
        
        if self.stats['start_time']:
            runtime = (datetime.now() - self.stats['start_time']).total_seconds()
            print(f"Runtime: {runtime:.1f} seconds")
        
        print("="*50 + "\n")
    
    def _print_help(self):
        """Print help message."""
        print("\n" + "="*50)
        print("CRAWLER COMMANDS")
        print("="*50)
        print("q, quit, exit, stop - Stop the crawler")
        print("s, stats, statistics - Show statistics")
        print("h, help - Show this help message")
        print("="*50 + "\n")
    
    def start(self, seed_urls: Optional[List[str]] = None):
        print("Starting Tübingen Crawler...")
        if seed_urls:
            self.add_seed_urls(seed_urls)
        else:
            # Load previous state or use default seeds
            self.load_previous_state()
            if len(self.frontier) == 0:
                print("No previous state found, using default seed URLs")
                self.add_seed_urls(DEFAULT_SEED_URLS)
        
        print(f"Frontier size: {len(self.frontier)}")
        print(f"Database: {self.config.db_path}")
        
        if self.config.enable_multiprocessing:
            print(f"Multiprocessing enabled with {self.config.max_workers} workers")
            self._start_multiprocessing_crawler()
        else:
            print("Single-threaded mode")
            self._start_single_threaded_crawler()
    
    def _start_multiprocessing_crawler(self):
        """Start the multiprocessing crawler."""
        try:
            mp_crawler = MultiprocessingCrawler(self.config, self)
            self.input_thread = threading.Thread(target=self._input_handler, daemon=True)
            self.input_thread.start()
            self.stats['start_time'] = datetime.now()
            self.is_running = True
            
            print("Multiprocessing crawler started. Commands: 'stats', 'stop', 'help'")
            mp_crawler.run()
            
        except KeyboardInterrupt:
            print("\nStopping multiprocessing crawler...")
            self.should_stop = True
            if 'mp_crawler' in locals():
                mp_crawler.stop()
        except Exception as e:
            print(f"Error in multiprocessing crawler: {e}")
            self.should_stop = True
        finally:
            self.is_running = False
            self.stats['end_time'] = datetime.now()
            if self.stats['start_time']:
                self.stats['total_runtime'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            print("\n" + "="*60)
            print("FINAL CRAWLING STATISTICS")
            print("="*60)
            self._print_statistics()
            if self.config.csv_export_enabled:
                print(f"\nExporting results to {self.config.csv_filename}...")
                self.db_manager.export_to_csv("urlsDB", self.config.csv_filename)
            
            print("Crawler stopped")
    
    def _start_single_threaded_crawler(self):
        """Start the single-threaded crawler (original behavior)."""
        try:
            self.input_thread = threading.Thread(target=self._input_handler, daemon=True)
            self.input_thread.start()
            self.stats['start_time'] = datetime.now()
            self.is_running = True
            
            print("Single-threaded crawler started. Commands: 'stats', 'stop', 'help'")
            self._crawl_loop()
            
        except KeyboardInterrupt:
            print("\nStopping crawler...")
            self.should_stop = True
        except Exception as e:
            print(f"Error in crawler: {e}")
            self.should_stop = True
        finally:
            self.is_running = False
            self.stats['end_time'] = datetime.now()
            if self.stats['start_time']:
                self.stats['total_runtime'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            print("\n" + "="*60)
            print("FINAL CRAWLING STATISTICS")
            print("="*60)
            self._print_statistics()

            if self.config.csv_export_enabled:
                print(f"\nExporting results to {self.config.csv_filename}...")
                self.db_manager.export_to_csv("urlsDB", self.config.csv_filename)
            
            print("Crawler stopped")
    
    def _crawl_loop(self):
        """Main crawling loop."""
        batch_count = 0
        consecutive_failures = 0
        max_consecutive_failures = 10
        
        while not self.should_stop and len(self.frontier) > 0:
            if consecutive_failures >= max_consecutive_failures:
                print(f"Too many consecutive failures ({consecutive_failures}), stopping...")
                break
            next_item = self.frontier.get_next_url()
            
            if not next_item:
                # No URLs ready, wait a bit
                time.sleep(1)
                continue
            
            url, entry = next_item
            # Check if we should stop before processing
            if self.should_stop:
                break
            
            # Crawl the URL with timeout protection
            try:
                success = self.crawl_url(url, entry)
                
                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                
                # Mark as crawled
                self.frontier.mark_crawled(url, success)
                self.stats['urls_processed'] += 1
                
            except Exception as e:
                print(f"Exception in crawl loop for {url}: {e}")
                consecutive_failures += 1
                try:
                    self.frontier.mark_crawled(url, False)
                except:
                    pass
                continue
            batch_count += 1
            if batch_count % self.config.max_pages_per_batch == 0:
                print(f"Completed batch {batch_count // self.config.max_pages_per_batch}")
                self._print_statistics()
                batch_count = 0
                
                # Small delay between batches
                if self.config.delay_between_batches > 0:
                    time.sleep(self.config.delay_between_batches / 1000.0)
            if self.should_stop:
                break
        
        if len(self.frontier) == 0:
            print("Frontier is empty. Crawling completed!")
        elif consecutive_failures >= max_consecutive_failures:
            print(f"Stopping due to {consecutive_failures} consecutive failures")
        else:
            print("Crawling stopped by user.")
    
    def stop(self):
        """Stop the crawler."""
        if not self.is_running:
            return
        
        print("Stopping crawler...")
        self.should_stop = True
        self.is_running = False
        self.stats['end_time'] = datetime.now()
        
        if self.stats['start_time']:
            self.stats['total_runtime'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        # Save frontier to database with timeout protection
        try:
            print("Saving frontier to database...")
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Frontier save timed out")
            
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)  # 10 second timeout
            
            try:
                self.frontier.save_to_database()
                print("Frontier saved successfully")
            finally:
                signal.signal(signal.SIGALRM, old_handler)
                signal.alarm(0)
                
        except Exception as e:
            print(f"Warning: Could not save frontier to database: {e}")
        
        # Export results if enabled with timeout protection
        if self.config.csv_export_enabled:
            try:
                print(f"Exporting results to {self.config.csv_filename}...")
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("CSV export timed out")
                
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(10)  # 10 second timeout
                
                try:
                    self.db_manager.export_to_csv("urlsDB", self.config.csv_filename)
                    print("CSV export completed")
                finally:
                    signal.signal(signal.SIGALRM, old_handler)
                    signal.alarm(0)
                    
            except Exception as e:
                print(f"Warning: Could not export CSV: {e}")

        try:
            self.http_client.close()
        except Exception as e:
            print(f"Warning: Could not close HTTP client: {e}")
        
        try:
            self.db_manager.close()
        except Exception as e:
            print(f"Warning: Could not close database: {e}")
        try:
            self._print_statistics()
        except Exception as e:
            print(f"Warning: Could not print final statistics: {e}")
        
        print("Crawler stopped successfully.")
        
        # Force exit if necessary (last resort)
        sys.exit(0)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get complete crawler statistics."""
        frontier_stats = self.frontier.get_statistics()
        db_stats = self.db_manager.get_statistics()
        
        return {
            'crawler_stats': self.stats.copy(),
            'frontier_stats': frontier_stats,
            'database_stats': db_stats
        }
    
    def load_previous_state(self):
        """Load previous crawling state from database."""
        print("Loading previous crawling state...")
        self.frontier.load_from_database()
        print(f"Loaded {len(self.frontier)} URLs from database")
    
    def clear_state(self):
        """Clear all crawling state."""
        print("Clearing crawling state...")
        self.frontier.clear_frontier()
        # Note: This doesn't clear the main URL database, only the frontier
        print("State cleared.")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop() 