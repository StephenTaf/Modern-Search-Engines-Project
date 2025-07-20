# Tübingen University Crawler

A large web crawler specifically designed for crawling Tübingen websites with multiprocessing support and tricky anti-ban protection.

## Quick Installation

```bash
# Create virtual environment (recommended)
python3 -m venv crawler-env
source crawler-env/bin/activate

# Install dependencies from root repository
pip install -r requirements.txt

# Test installation
python3 -m crawler.main --help
```

## Features

- **Multiprocessing Support**: Parallel crawling with configurable workers
- **Anti-Ban Protection**: Respectful crawling with domain delays and rate limiting
- **Graceful Shutdown**: Proper job completion during termination
- **Domain-Based Parallelization**: Prevents overwhelming individual websites
- **Super Scoring**: Tübingen-specific content relevance scoring based on experiments
- **Robust Error Handling**: Comprehensive error logging and recovery

## Graceful Shutdown

The crawler includes graceful shutdown that ensures all jobs are completed properly:

### What happens during shutdown:

1. **Signal Detection**: Responds to SIGINT (Ctrl+C) and SIGTERM signals
2. **Worker Notification**: Sends stop signals to all worker processes
3. **Batch Completion**: Workers finish their current batch before stopping
4. **Result Processing**: Main process continues processing all remaining results
5. **Worker Coordination**: Waits for all workers to finish gracefully
6. **Final Cleanup**: Processes any final results and closes connections

#### Thus...:

- **No Lost Results**: All processed URLs are saved to the database
- **Proper Cleanup**: HTTP connections and resources are closed correctly
- **Coordinated Shutdown**: Workers and main process coordinate shutdown
- **Timeout Protection**: Reasonable timeouts prevent hanging processes
- **Progress Reporting**: Clear shutdown progress messages


## Quick Start

### Basic crawling:
```bash
# Single-threaded crawling
python -m crawler.main

# Multiprocessing crawling (recommended! But sometimes may take some time to stop)
python -m crawler.main --multiprocessing --max-workers 4
```

### Advanced configuration:
```bash
# Custom multiprocessing settings
python -m crawler.main \
    --multiprocessing \
    --max-workers 6 \
    --domain-delay 3.0 \
    --batch-size 5

# Using SOCKS5 proxy
python -m crawler.main \
    --proxy "socks5://username:password@host:port" \
    --proxy-timeout 30

# Using HTTP proxy
python -m crawler.main \
    --proxy "http://username:password@host:port"

# Multiprocessing with proxy (best approach)
python -m crawler.main \
    --multiprocessing \
    --max-workers 4 \
    --proxy "socks5://username:password@host:port"
```

## Configuration

### Multiprocessing Settings

- `enable_multiprocessing`: Enable parallel processing (default: False)
- `max_workers`: Number of worker processes (default: 4)
- `urls_per_worker_batch`: URLs per batch sent to workers (default: 10)
- `domain_rotation_delay`: Delay between requests to same domain (default: 5.0s)
- `worker_coordination_delay`: Delay for worker coordination (default: 1.0s)

### Safety Features

- **Domain Delays**: Prevents overwhelming individual websites
- **Rate Limiting**: Respects HTTP 429 responses
- **Robots.txt Compliance**: Follows website crawling rules
- **Cloudflare Protection**: Handles protected sites gracefully

### Proxy Configuration

- `use_proxy`: Enable proxy usage (default: False)
- `proxy_url`: Proxy URL in format "protocol://user:pass@host:port"
- `proxy_timeout`: Proxy connection timeout in seconds (default: 30)

**Supported proxy types:**
- **SOCKS5**: `socks5://username:password@host:port`
- **HTTP/HTTPS**: `http://username:password@host:port`

**Example proxy usage:**
```python
config = CrawlerConfig(
    use_proxy=True,
    proxy_url="socks5://user:pass@175.29.6.31:12324",
    proxy_timeout=30
)
```

## Architecture

### Single-Threaded Mode
```
Main Process → HTTP Client → Text Processor → Database
```

### Multiprocessing Mode
```
Main Process:
├── URL Distribution
├── Result Processing  
├── Database Operations
└── Scoring

Workers (N processes):
├── HTTP Requests
├── Text Extraction
└── Result Sending
```


## Database Schema

### Tables Created:
- `urlsDB`: Successfully crawled URLs with content and scores
- `frontier`: Pending URLs for crawling
- `disallowed`: URLs blocked by robots.txt
- `errors`: Error logs with details


## Loop Prevention

The crawler has **robust loop prevention** to ensure it never visits pages that have already been crawled:
