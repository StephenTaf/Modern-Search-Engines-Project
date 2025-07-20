#!/usr/bin/env python3
"""CLI for the Tübingen crawler."""

import argparse
import sys
from typing import List

from .config import CrawlerConfig, DEFAULT_SEED_URLS
from .crawler import TuebingenCrawler


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Tübingen web crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m crawler.main                           # Run with automatic state loading
  python -m crawler.main --seeds url1 url2        # Custom seed URLs
  python -m crawler.main --max-pages 50           # Limit pages per batch
  python -m crawler.main --timeout 10             # Set request timeout
  python -m crawler.main --fresh-start            # Start fresh (ignore previous state)
  python -m crawler.main --clear-state            # Clear previous state and exit
  python -m crawler.main --multiprocessing        # Enable multiprocessing (4 workers)
  python -m crawler.main --multiprocessing --max-workers 8 --domain-delay 3.0  # 8 workers with 3s domain delay
  python -m crawler.main --multiprocessing --urls-per-batch 20  # Larger batches per worker
        """
    )
    parser.add_argument(
        '--seeds', 
        nargs='+', 
        help='Seed URLs to start crawling from'
    )
    
    parser.add_argument(
        '--max-pages', 
        type=int, 
        default=100,
        help='Maximum pages to process per batch'
    )
    
    parser.add_argument(
        '--delay', 
        type=int, 
        default=100,
        help='Delay between batches in milliseconds'
    )
    
    parser.add_argument(
        '--timeout', 
        type=int, 
        default=5,
        help='Request timeout in seconds'
    )
    parser.add_argument(
        '--proxy', 
        type=str,
        help='Proxy URL (e.g., socks5://user:pass@host:port or http://user:pass@host:port)'
    )
    
    parser.add_argument(
        '--proxy-timeout', 
        type=int, 
        default=30,
        help='Proxy timeout in seconds'
    )
    parser.add_argument(
        '--multiprocessing', 
        action='store_true',
        help='Enable multiprocessing for faster crawling'
    )
    
    parser.add_argument(
        '--max-workers', 
        type=int, 
        default=4,
        help='Maximum number of worker processes'
    )
    
    parser.add_argument(
        '--urls-per-batch', 
        type=int, 
        default=10,
        help='URLs per worker batch'
    )
    
    parser.add_argument(
        '--domain-delay', 
        type=float, 
        default=5.0,
        help='Delay between processing URLs from same domain in seconds'
    )
    parser.add_argument(
        '--db-path', 
        default='crawler.db',
        help='Database file path (default: crawler.db)'
    )
    
    parser.add_argument(
        '--csv-output', 
        default='crawled_urls.csv',
        help='CSV output file path (default: crawled_urls.csv)'
    )
    
    parser.add_argument(
        '--no-csv', 
        action='store_true',
        help='Disable CSV export'
    )
    
    parser.add_argument(
        '--fresh-start', 
        action='store_true',
        help='Start fresh, ignoring any previous crawling state'
    )
    
    parser.add_argument(
        '--clear-state', 
        action='store_true',
        help='Clear previous crawling state and exit'
    )
    parser.add_argument(
        '--load-state', 
        action='store_true',
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        '--utema-beta', 
        type=float, 
        default=0.2,
        help='UTEMA beta parameter for exponential smoothing'
    )
    
    return parser.parse_args()


def create_config(args: argparse.Namespace) -> CrawlerConfig:
    """Create crawler configuration from arguments."""
    return CrawlerConfig(
        timeout=args.timeout,
        db_path=args.db_path,
        max_pages_per_batch=args.max_pages,
        delay_between_batches=args.delay,
        enable_multiprocessing=args.multiprocessing,
        max_workers=args.max_workers,
        urls_per_worker_batch=args.urls_per_batch,
        domain_rotation_delay=args.domain_delay,
        utema_beta=args.utema_beta,
        csv_export_enabled=not args.no_csv,
        csv_filename=args.csv_output,
        use_proxy=bool(args.proxy),
        proxy_url=args.proxy,
        proxy_timeout=args.proxy_timeout
    )


def main():
    """Main entry point for the crawler CLI."""
    args = parse_arguments()
    config = create_config(args)
    print("Initializing Tübingen Crawler...")
    crawler = TuebingenCrawler(config)
    try:
        # Handle state management
        if args.clear_state:
            crawler.clear_state()
            print("Cleared previous crawling state.")
            return
        
        # Check if we should load previous state
        should_load_state = not args.fresh_start  # Load by default unless fresh start
        
        if should_load_state:
            # Check if there's existing state to load
            try:
                print("Checking for previous crawling state...")
                frontier_stats = crawler.frontier.get_statistics()
                
                # Try to load state - if there's meaningful state, it will load
                crawler.load_previous_state()
                
                # Check if we actually loaded anything
                new_frontier_stats = crawler.frontier.get_statistics()
                if new_frontier_stats['frontier_size'] > 0:
                    print(f"[!] Loaded previous state: {new_frontier_stats['frontier_size']} URLs in frontier")
                    print(f"   Previously visited: {new_frontier_stats['visited_count']} URLs")
                    print("   Resuming crawling from where you left off...")
                else:
                    print("[!]  No previous state found - starting fresh")
                    
            except Exception as e:
                print(f"[!] Could not load previous state: {e}")
                print("   Starting fresh...")
        else:
            print("[!] Starting fresh (ignoring any previous state)")
        
        # Determine seed URLs
        seed_urls = args.seeds if args.seeds else None
        
        # Only add seed URLs if we're starting fresh or have no existing frontier
        frontier_size = crawler.frontier.get_statistics()['frontier_size']
        if frontier_size == 0 and seed_urls is None:
            print("   Using default Tübingen seed URLs")
        elif frontier_size == 0 and seed_urls:
            print(f"   Using {len(seed_urls)} custom seed URLs")
        elif frontier_size > 0:
            seed_urls = []
            print("   Continuing with existing frontier URLs")
        print("\nCrawler Configuration:")
        print(f"  Database: {config.db_path}")
        print(f"  Max pages per batch: {config.max_pages_per_batch}")
        print(f"  Request timeout: {config.timeout}s")
        print(f"  Delay between batches: {config.delay_between_batches}ms")
        print(f"  CSV export: {'enabled' if config.csv_export_enabled else 'disabled'}")
        if config.csv_export_enabled:
            print(f"  CSV file: {config.csv_filename}")
        print(f"  UTEMA beta: {config.utema_beta}")
        
        print("\nStarting crawler...")
        print("Interactive commands: 'q' to quit, 's' for stats, 'h' for help\n")
        
        # Start crawling
        crawler.start(seed_urls)
        
    except KeyboardInterrupt:
        print("\nCrawler interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if hasattr(crawler, 'is_running') and crawler.is_running:
            crawler.stop()


if __name__ == '__main__':
    main() 