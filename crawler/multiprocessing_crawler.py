"""Multiprocessing support for the Tübingen crawler."""

import multiprocessing
import time
import queue
import threading
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from urllib.parse import urlparse
from multiprocessing import Process, Queue, Manager
import signal

from .config import CrawlerConfig
from .database import DatabaseManager
from .http_client import HttpClient
from .url_manager import UrlManager
from .text_processor import TextProcessor
from .scoring import ContentScorer
from .frontier import FrontierManager, FrontierEntry


class EfficientDomainScheduler:
    """Efficient domain delay management with event-based scheduling."""
    
    def __init__(self, manager):
        self.domain_delays = manager.dict()  # domain -> delay_seconds
        self.domain_ready_times = manager.dict()  # domain -> next_ready_time
        self.global_lock = manager.Lock()
    
    def get_domain_delay(self, domain: str) -> float:
        """Get the required delay for a domain."""
        return self.domain_delays.get(domain, 0.1)  # Reduced default delay
    
    def set_domain_delay(self, domain: str, delay: float):
        """Set the delay for a domain."""
        with self.global_lock:
            self.domain_delays[domain] = delay
    
    def get_ready_time(self, domain: str) -> float:
        """Get the time when domain will be ready for next request."""
        current_time = time.time()
        return self.domain_ready_times.get(domain, current_time)
    
    def is_domain_ready(self, domain: str) -> bool:
        """Check if a domain is ready for crawling."""
        current_time = time.time()
        ready_time = self.domain_ready_times.get(domain, current_time)
        return current_time >= ready_time
    
    def schedule_domain_access(self, domain: str) -> float:
        """Schedule the next access time for a domain and return wait time."""
        current_time = time.time()
        delay = self.get_domain_delay(domain)
        
        with self.global_lock:
            # Get the time when this domain was last accessed
            last_ready_time = self.domain_ready_times.get(domain, current_time - delay)
            
            # Calculate when the domain will be ready for next access
            next_ready_time = last_ready_time + delay
            
            # Update the domain's next ready time
            self.domain_ready_times[domain] = max(current_time, next_ready_time)
            
            # Return wait time (0 if ready now)
            wait_time = max(0, next_ready_time - current_time)
            return wait_time


class BackgroundDatabaseWriter:
    """Background thread for handling database operations asynchronously."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.write_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.stats = {
            'urls_written': 0,
            'errors_logged': 0,
            'operations_processed': 0
        }
    
    def start(self):
        """Start the background database writer thread."""
        self.thread = threading.Thread(target=self._writer_loop, daemon=True)
        self.thread.start()
        print("Background database writer started")
    
    def stop(self):
        """Stop the background database writer thread."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.db_manager.close()
        print(f"Background database writer stopped. Stats: {self.stats}")
    
    def queue_url_insert(self, url: str, text: str, title: Optional[str], score: float, linking_depth: int,
                         domain_linking_depth: int, parent_url: Optional[str],
                         status_code: int, content_type: Optional[str],
                         last_modified: Optional[str], etag: Optional[str]):
        """Queue a URL insert operation."""
        operation = {
            'type': 'insert_url',
            'data': {
                'url': url,
                'text': text,
                'title': title,
                'score': score,
                'linking_depth': linking_depth,
                'domain_linking_depth': domain_linking_depth,
                'parent_url': parent_url,
                'status_code': status_code,
                'content_type': content_type,
                'last_modified': last_modified,
                'etag': etag
            }
        }
        self.write_queue.put(operation)
    
    def queue_error_log(self, url: str, error_type: str, error_message: str, status_code: Optional[int] = None):
        """Queue an error logging operation."""
        operation = {
            'type': 'log_error',
            'data': {
                'url': url,
                'error_type': error_type,
                'error_message': error_message,
                'status_code': status_code
            }
        }
        self.write_queue.put(operation)
    
    def _writer_loop(self):
        """Main loop for the background database writer."""
        batch_operations = []
        batch_timeout = 0.5  # Process batches every 500ms
        last_batch_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Try to get operations from queue
                try:
                    operation = self.write_queue.get(timeout=0.1)
                    batch_operations.append(operation)
                except queue.Empty:
                    pass
                
                # Process batch if timeout reached or stop event set
                current_time = time.time()
                if (batch_operations and 
                    (current_time - last_batch_time >= batch_timeout or 
                     self.stop_event.is_set() or 
                     len(batch_operations) >= 10)):  # Also process when batch is large enough
                    
                    self._process_batch(batch_operations)
                    batch_operations.clear()
                    last_batch_time = current_time
                    
            except Exception as e:
                print(f"Background database writer error: {e}")
                time.sleep(0.1)
        
        # Process any remaining operations
        if batch_operations:
            self._process_batch(batch_operations)
    
    def _process_batch(self, operations: List[Dict[str, Any]]):
        """Process a batch of database operations."""
        try:
            for operation in operations:
                if operation['type'] == 'insert_url':
                    data = operation['data']
                    self.db_manager.insert_url(**data)
                    self.stats['urls_written'] += 1
                elif operation['type'] == 'log_error':
                    data = operation['data']
                    self.db_manager.log_error(**data)
                    self.stats['errors_logged'] += 1
                
                self.stats['operations_processed'] += 1
        
        except Exception as e:
            print(f"Error processing database batch: {e}")


def worker_process_function(worker_id: int, config_dict: Dict[str, Any], 
                          url_queue: Queue, result_queue: Queue, 
                          shared_delays: EfficientDomainScheduler, stop_event):
    """Worker process function that can be pickled."""
    try:
        # Recreate config from dictionary
        config = CrawlerConfig(**config_dict)
        
        # Initialize HTTP client and URL manager for URL extraction
        http_client = HttpClient(config)
        text_processor = TextProcessor()
        url_manager = UrlManager(config, http_client)
        
        print(f"Worker {worker_id}: Started")
        
        while not stop_event.is_set():
            try:
                # Get URLs from queue (with timeout)
                urls_batch = url_queue.get(timeout=1.0)
                
                if urls_batch is None:  # Poison pill to stop worker
                    break
                
                # Process URLs in this batch with interruption checking
                for url, entry_data in urls_batch:
                    # Check stop event before processing each URL
                    if stop_event.is_set():
                        print(f"Worker {worker_id}: Stopping mid-batch due to stop signal")
                        break
                    
                    domain = urlparse(url).netloc
                    
                    # PERFORMANCE FIX: Efficient domain scheduling instead of busy waiting
                    wait_time = shared_delays.schedule_domain_access(domain)
                    if wait_time > 0:
                        time.sleep(min(wait_time, 1.0))  # Limit wait time for faster interruption
                    
                    # Check stop event again after waiting
                    if stop_event.is_set():
                        print(f"Worker {worker_id}: Stopping after domain wait")
                        break
                    
                    print(f"Worker {worker_id}: Processing {url}")
                    
                    try:
                        # Check if URL is allowed by robots.txt
                        if not url_manager.is_url_allowed_fast(url):
                            result_queue.put({
                                'type': 'skipped',
                                'worker_id': worker_id,
                                'url': url,
                                'reason': 'robots.txt disallowed'
                            })
                            continue

                        # Make HTTP request
                        response, error = http_client.get(url)
                        
                        if error:
                            result_queue.put({
                                'type': 'error',
                                'worker_id': worker_id,
                                'url': url,
                                'error_type': 'http_error',
                                'error_message': error
                            })
                            continue
                        
                        if not response or not http_client.is_success(response):
                            status_code = response.status_code if response else 0
                            result_queue.put({
                                'type': 'error',
                                'worker_id': worker_id,
                                'url': url,
                                'error_type': 'http_status',
                                'error_message': f"HTTP {status_code}",
                                'status_code': status_code
                            })
                            continue
                        
                        # Check if HTML content
                        if not http_client.is_html_content(response):
                            result_queue.put({
                                'type': 'skipped',
                                'worker_id': worker_id,
                                'url': url,
                                'reason': 'non-html-content'
                            })
                            continue
                        
                        # PERFORMANCE OPTIMIZATION: Limit content size for processing
                        html_content = response.text
                        content_size = len(html_content)
                        
                        # Skip extremely large pages that would be slow to process
                        if content_size > 5 * 1024 * 1024:  # 5MB limit
                            result_queue.put({
                                'type': 'skipped',
                                'worker_id': worker_id,
                                'url': url,
                                'reason': 'content-too-large',
                                'content_size': content_size
                            })
                            continue
                        
                        # Use truncated content for large pages to speed up processing
                        processing_content = html_content
                        if content_size > 1024 * 1024:  # 1MB
                            # For large pages, use first 1MB for text extraction and first 500KB for URL extraction
                            processing_content = html_content[:1024*1024]
                            print(f"Worker {worker_id}: Large page ({content_size} bytes), using truncated content")
                        
                        # PERFORMANCE FIX: Always use fast text extraction for consistent performance
                        try:
                            text_content = text_processor.extract_text_fast(processing_content)
                        except Exception as e:
                            print(f"Worker {worker_id}: Text extraction failed for {url}: {e}")
                            text_content = ""
                        
                        # Extract page title
                        try:
                            title = text_processor.extract_title(html_content)
                        except Exception as e:
                            print(f"Worker {worker_id}: Title extraction failed for {url}: {e}")
                            title = None
                        
                        if not text_content or len(text_content.strip()) < 50:
                            result_queue.put({
                                'type': 'skipped',
                                'worker_id': worker_id,
                                'url': url,
                                'reason': 'insufficient-content'
                            })
                            continue
                        
                        # PERFORMANCE FIX: Always use fast URL extraction with size limits
                        extracted_urls = []
                        try:
                            # For URL extraction, use smaller content sample for large pages
                            url_extraction_content = html_content
                            if content_size > 500 * 1024:  # 500KB
                                # Use first 500KB for URL extraction to speed up regex processing
                                url_extraction_content = html_content[:500*1024]
                            
                            # Always use fast extraction for consistent performance
                            new_urls = url_manager.extract_urls_fast(url_extraction_content, url, max_urls=1000)
                            
                            # Basic filtering that doesn't require database access
                            for new_url in new_urls:
                                # Skip obvious duplicates and invalid URLs
                                if (new_url != url and 
                                    new_url.startswith(('http://', 'https://')) and
                                    len(new_url) < 2000):  # Reasonable URL length limit
                                    extracted_urls.append(new_url)
                            
                            # Limit number of URLs extracted to prevent memory issues
                            if len(extracted_urls) > 1000:
                                extracted_urls = extracted_urls[:1000]
                                
                        except Exception as e:
                            print(f"Worker {worker_id}: Error extracting URLs from {url}: {e}")
                        
                        print(f"Worker {worker_id}: Processed {url} ({content_size} bytes, {len(extracted_urls)} URLs)")
                        
                        # Send successful result back to main process (without full HTML)
                        result_queue.put({
                            'type': 'success',
                            'worker_id': worker_id,
                            'url': url,
                            'text': text_content,
                            'title': title,
                            'extracted_urls': extracted_urls,  # Send extracted URLs instead of HTML
                            'status_code': response.status_code,
                            'content_type': http_client.get_content_type(response),
                            'last_modified': http_client.get_last_modified(response),
                            'etag': http_client.get_etag(response),
                            'entry_data': entry_data
                        })
                        
                        # Domain delay
                        domain_delay = shared_delays.get_domain_delay(domain)
                        if domain_delay > 0:
                            time.sleep(domain_delay)
                            
                    except Exception as e:
                        result_queue.put({
                            'type': 'error',
                            'worker_id': worker_id,
                            'url': url,
                            'error_type': 'exception',
                            'error_message': str(e)
                        })
                
                # Send batch completion signal
                result_queue.put({
                    'type': 'batch_complete',
                    'worker_id': worker_id
                })
                        
            except queue.Empty:
                continue  # Check for stop signal
            except Exception as e:
                print(f"Worker {worker_id}: Error in main loop: {e}")
                break
    
    except Exception as e:
        print(f"Worker {worker_id}: Error during initialization: {e}")
        
    finally:
        # Send worker finished signal
        try:
            result_queue.put({
                'type': 'worker_finished',
                'worker_id': worker_id
            }, timeout=1.0)
        except queue.Full:
            pass  # Queue might be full during shutdown
        
        # Cleanup
        if 'http_client' in locals():
            http_client.close()
        print(f"Worker {worker_id}: Stopped")


class MultiprocessingCrawler:
    """Multiprocessing-aware crawler coordinator."""
    
    def __init__(self, config: CrawlerConfig, main_crawler):
        self.config = config
        self.main_crawler = main_crawler
        self.workers = []
        self.should_stop = False
        
        # PERFORMANCE FIX: Use background database writer instead of synchronous operations
        self.db_writer = BackgroundDatabaseWriter(config)
        
        # Multiprocessing components
        self.manager = Manager()
        self.url_queue = Queue()
        self.result_queue = Queue()
        self.shared_delays = EfficientDomainScheduler(self.manager)
        
        # Add shared stop event for immediate worker interruption
        self.stop_event = self.manager.Event()
        
        # Statistics
        self.mp_stats = {
            'total_workers': 0,
            'active_workers': 0,
            'urls_distributed': 0,
            'batches_processed': 0,
            'worker_stats': {}
        }
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            print(f"Multiprocessing coordinator: Received signal {signum}, stopping...")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def start_workers(self):
        """Start worker processes."""
        print(f"Starting {self.config.max_workers} worker processes...")
        
        # Start background database writer
        self.db_writer.start()
        
        # Convert config to dictionary for pickling
        config_dict = {
            'timeout': self.config.timeout,
            'simulate_human_behavior': self.config.simulate_human_behavior,
            'use_cloudscraper_fallback': self.config.use_cloudscraper_fallback,
            'cloudscraper_timeout': self.config.cloudscraper_timeout,
            'cloudscraper_delay': self.config.cloudscraper_delay,
            'cloudscraper_browser': self.config.cloudscraper_browser,
            'cloudscraper_platform': self.config.cloudscraper_platform,
            'respect_rate_limits': self.config.respect_rate_limits,
            'default_rate_limit_wait': self.config.default_rate_limit_wait
        }
        
        for i in range(self.config.max_workers):
            process = Process(
                target=worker_process_function,
                args=(i, config_dict, self.url_queue, self.result_queue, self.shared_delays, self.stop_event)
            )
            process.start()
            
            self.workers.append({
                'process': process,
                'id': i
            })
        
        self.mp_stats['total_workers'] = len(self.workers)
        self.mp_stats['active_workers'] = len(self.workers)
    
    def distribute_urls(self):
        """Distribute URLs from frontier to workers with optimized batching."""
        consecutive_empty_batches = 0
        max_empty_batches = 10  # Prevent infinite loops
        
        while not self.should_stop and (len(self.main_crawler.frontier) > 0 or 
                                       any(worker['process'].is_alive() for worker in self.workers)):
            
            # PERFORMANCE FIX: Create domain-diverse batches
            urls_batch = []
            seen_domains = set()
            attempts = 0
            max_attempts = self.config.urls_per_worker_batch * 2  # Try harder to fill batch
            
            print(f"Attempting to distribute URLs. Frontier size: {len(self.main_crawler.frontier)}")
            
            while len(urls_batch) < self.config.urls_per_worker_batch and attempts < max_attempts:
                next_item = self.main_crawler.frontier.get_next_url()
                if next_item:
                    url, entry = next_item
                    domain = urlparse(url).netloc
                    
                    # Prefer URLs from different domains for better parallelization
                    if domain not in seen_domains or len(urls_batch) < self.config.urls_per_worker_batch // 2:
                        seen_domains.add(domain)
                        # Convert entry to dictionary for pickling
                        entry_data = {
                            'linking_depth': entry.linking_depth,
                            'domain_linking_depth': entry.domain_linking_depth,
                            'parent_url': entry.parent_url
                        }
                        urls_batch.append((url, entry_data))
                    else:
                        # Put back URL if we have too many from this domain
                        self.main_crawler.frontier.add_url(
                            url, entry.parent_url, 
                            entry.linking_depth, 
                            entry.domain_linking_depth
                        )
                else:
                    break
                attempts += 1
            
            if urls_batch:
                consecutive_empty_batches = 0  # Reset counter
                try:
                    # Reduced timeout for faster response
                    self.url_queue.put(urls_batch, timeout=0.5)
                    self.mp_stats['urls_distributed'] += len(urls_batch)
                    print(f"Distributed {len(urls_batch)} URLs from {len(seen_domains)} domains to workers")
                except queue.Full:
                    # Put URLs back to frontier if queue is full
                    for url, entry_data in urls_batch:
                        self.main_crawler.frontier.add_url(
                            url, entry_data['parent_url'], 
                            entry_data['linking_depth'], 
                            entry_data['domain_linking_depth']
                        )
                    break
            else:
                consecutive_empty_batches += 1
                print(f"No URLs ready for distribution (attempt {consecutive_empty_batches}/{max_empty_batches}). Frontier size: {len(self.main_crawler.frontier)}")
                
                # If we can't get URLs for too long, check if all workers are idle
                if consecutive_empty_batches >= max_empty_batches:
                    active_workers = sum(1 for worker in self.workers if worker['process'].is_alive())
                    if active_workers == 0 or len(self.main_crawler.frontier) == 0:
                        print("No URLs available and workers idle. Stopping distribution.")
                        break
                    else:
                        print(f"Waiting for URLs to become ready. Active workers: {active_workers}")
                        consecutive_empty_batches = 0  # Reset and continue trying
            
            # Process results from workers
            self.process_worker_results()
            
            # Reduced delay for faster coordination
            time.sleep(self.config.worker_coordination_delay)
    
    def process_worker_results(self):
        """Process results from worker processes with batching optimization."""
        results_processed = 0
        max_batch_size = 20  # Process up to 20 results per call
        
        while results_processed < max_batch_size:
            try:
                result = self.result_queue.get_nowait()
                results_processed += 1
                
                if result['type'] == 'success':
                    # Process successful crawl in main process
                    self.handle_successful_crawl(result)
                    
                elif result['type'] == 'error':
                    # Queue error for background processing
                    self.db_writer.queue_error_log(
                        result['url'], 
                        result['error_type'], 
                        result['error_message'],
                        result.get('status_code')
                    )
                    print(f"Worker {result['worker_id']}: Error - {result['error_message']}")
                    
                elif result['type'] == 'batch_complete':
                    self.mp_stats['batches_processed'] += 1
                    print(f"Worker {result['worker_id']}: Batch completed")
                    
                elif result['type'] == 'skipped':
                    print(f"Worker {result['worker_id']}: Skipped {result['url']} - {result['reason']}")
            
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error processing worker result: {e}")
                break
        
        # Report batch processing if any results were processed
        if results_processed > 0:
            print(f"Processed {results_processed} worker results in batch")
    
    def handle_successful_crawl(self, result: Dict[str, Any]):
        """Handle successful crawl result from worker."""
        try:
            # Calculate score using main crawler's scorer
            score = self.main_crawler.scorer.calculate_final_score(
                url=result['url'],
                text=result['text'],
                linking_depth=result['entry_data']['linking_depth']
            )
            
            # Store in main database using our own db_manager
            self.db_writer.queue_url_insert(
                url=result['url'],
                text=result['text'],
                title=result['title'],
                score=score,
                linking_depth=result['entry_data']['linking_depth'],
                domain_linking_depth=result['entry_data']['domain_linking_depth'],
                parent_url=result['entry_data']['parent_url'],
                status_code=result['status_code'],
                content_type=result['content_type'],
                last_modified=result['last_modified'],
                etag=result['etag']
            )
            
            # Extract and add new URLs to frontier (CRITICAL FIX)
            if 'extracted_urls' in result:
                new_urls = result['extracted_urls']
                visited_urls = self.main_crawler.frontier.visited_urls.union(
                    self.main_crawler.frontier.crawled_urls
                )
                disallowed_urls = set()  # Could be loaded from database
                
                # PERFORMANCE FIX: Use fast filtering to avoid robots.txt bottleneck
                filtered_urls = self.main_crawler.url_manager.filter_urls_fast(
                    new_urls, result['url'], visited_urls, disallowed_urls
                )
                
                # Add new URLs to frontier
                for new_url in filtered_urls:
                    self.main_crawler.frontier.add_url(
                        new_url,
                        parent_url=result['url'],
                        linking_depth=result['entry_data']['linking_depth'] + 1,
                        domain_linking_depth=result['entry_data']['domain_linking_depth'] + 1
                    )
                
                url_count_msg = f", found {len(filtered_urls)} new URLs"
            else:
                url_count_msg = " (no URLs extracted for frontier update)"
            
            # Update crawler stats
            self.main_crawler.stats['urls_successful'] += 1
            self.main_crawler.stats['urls_processed'] += 1
            
            # Mark as crawled in frontier
            self.main_crawler.frontier.mark_crawled(result['url'], True)
            
            # DOMAIN TRACKING: Update domain page count for successful crawl
            self.main_crawler.frontier.update_domain_page_count(result['url'])
            
            print(f"Worker {result['worker_id']}: Successfully processed {result['url']} (score: {score:.4f}){url_count_msg}")
            
        except Exception as e:
            print(f"Error handling successful crawl for {result['url']}: {e}")
            self.main_crawler.stats['urls_failed'] += 1
    
    def stop(self):
        """Stop all worker processes immediately using stop event."""
        self.should_stop = True
        
        print("Stopping multiprocessing crawler...")
        
        # Set stop event to interrupt workers immediately (even mid-batch)
        self.stop_event.set()
        print("Stop signal sent to all workers")
        
        # Send poison pills to workers (backup method)
        for _ in self.workers:
            try:
                self.url_queue.put(None, timeout=0.1)  # Reduced timeout
            except queue.Full:
                pass
        
        # Give workers a short time to finish current requests and respond
        print("Waiting for workers to finish current requests...")
        
        # Process remaining results with shorter timeout
        active_workers = len(self.workers)
        final_results_timeout = 10  # Reduced from 30 to 10 seconds
        
        while active_workers > 0 and final_results_timeout > 0:
            # Process any remaining results
            results_processed = 0
            try:
                while True:
                    result = self.result_queue.get_nowait()
                    
                    if result['type'] == 'success':
                        self.handle_successful_crawl(result)
                        results_processed += 1
                    elif result['type'] == 'error':
                        self.db_writer.queue_error_log(
                            result['url'], 
                            result['error_type'], 
                            result['error_message'],
                            result.get('status_code')
                        )
                    elif result['type'] == 'batch_complete':
                        self.mp_stats['batches_processed'] += 1
                    elif result['type'] == 'skipped':
                        results_processed += 1
                    elif result['type'] == 'worker_finished':
                        print(f"Worker {result['worker_id']}: Finished gracefully")
                        active_workers -= 1
                        
            except queue.Empty:
                pass
            
            # Check if any workers are still alive
            alive_workers = sum(1 for worker in self.workers if worker['process'].is_alive())
            if alive_workers < active_workers:
                active_workers = alive_workers
            
            if results_processed == 0:
                time.sleep(0.1)  # Small delay if no results processed
                final_results_timeout -= 0.1
            else:
                print(f"Processed {results_processed} final results")
        
        # More aggressive joining with shorter timeout
        print("Joining worker processes...")
        for worker_info in self.workers:
            worker_info['process'].join(timeout=2)  # Reduced from 5 to 2 seconds
            if worker_info['process'].is_alive():
                print(f"Terminating worker {worker_info['id']} (didn't finish gracefully)")
                worker_info['process'].terminate()
                worker_info['process'].join(timeout=1)  # Reduced timeout
        
        # Process any final results that might have been queued
        print("Processing final results...")
        final_count = 0
        try:
            while True:
                result = self.result_queue.get_nowait()
                if result['type'] == 'success':
                    self.handle_successful_crawl(result)
                    final_count += 1
                elif result['type'] == 'error':
                    self.db_writer.queue_error_log(
                        result['url'], 
                        result['error_type'], 
                        result['error_message'],
                        result.get('status_code')
                    )
                    final_count += 1
        except queue.Empty:
            pass
        
        if final_count > 0:
            print(f"Processed {final_count} final results after worker shutdown")
        
        print("All workers stopped and results processed")
        
        # Close database manager
        self.db_writer.stop()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get multiprocessing statistics."""
        return {
            'multiprocessing': self.mp_stats,
            'shared_delays': {
                'domains_tracked': len(self.shared_delays.domain_delays),
                'domain_delays': dict(self.shared_delays.domain_delays)
            },
            'background_database': self.db_writer.stats
        }
    
    def run(self):
        """Run the multiprocessing crawler."""
        self.setup_signal_handlers()
        
        try:
            self.start_workers()
            self.distribute_urls()
        finally:
            self.stop() 