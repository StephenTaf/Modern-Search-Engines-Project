# Tübingen University Crawler

A sophisticated web crawler specifically designed for crawling Tübingen University websites with multiprocessing support and anti-ban protection.

## Quick Installation

```bash
# Create virtual environment (recommended)
python3 -m venv crawler-env
source crawler-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Test installation
python3 -m crawler.main --help
```

**For detailed installation instructions, platform-specific notes, and troubleshooting, see [INSTALL.md](../INSTALL.md).**

## Features

- **Multiprocessing Support**: Parallel crawling with configurable workers
- **Anti-Ban Protection**: Respectful crawling with domain delays and rate limiting
- **Graceful Shutdown**: Proper job completion during termination
- **Domain-Based Parallelization**: Prevents overwhelming individual websites
- **Intelligent Scoring**: Tübingen-specific content relevance scoring
- **Robust Error Handling**: Comprehensive error logging and recovery

## Graceful Shutdown

The crawler now includes **improved graceful shutdown** that ensures all jobs are completed properly:

### What happens during shutdown:

1. **Signal Detection**: Responds to SIGINT (Ctrl+C) and SIGTERM signals
2. **Worker Notification**: Sends stop signals to all worker processes
3. **Batch Completion**: Workers finish their current batch before stopping
4. **Result Processing**: Main process continues processing all remaining results
5. **Worker Coordination**: Waits for all workers to finish gracefully
6. **Final Cleanup**: Processes any final results and closes connections

### Key improvements:

- **No Lost Results**: All processed URLs are saved to the database
- **Proper Cleanup**: HTTP connections and resources are closed correctly
- **Coordinated Shutdown**: Workers and main process coordinate shutdown
- **Timeout Protection**: Reasonable timeouts prevent hanging processes
- **Progress Reporting**: Clear shutdown progress messages

### Testing graceful shutdown:

```bash
# Test graceful shutdown behavior
python -m crawler.test_graceful_shutdown

# Or use the regular crawler and press Ctrl+C
python -m crawler.main --multiprocessing --max-workers 3
```

## Quick Start

### Basic crawling:
```bash
# Single-threaded crawling
python -m crawler.main

# Multiprocessing crawling (recommended)
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

# With custom timeout and human behavior
python -m crawler.main \
    --multiprocessing \
    --max-workers 4 \
    --timeout 20 \
    --simulate-human-behavior

# Using SOCKS5 proxy
python -m crawler.main \
    --proxy "socks5://username:password@host:port" \
    --proxy-timeout 30

# Using HTTP proxy
python -m crawler.main \
    --proxy "http://username:password@host:port"

# Multiprocessing with proxy
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
- **Human Behavior Simulation**: Realistic crawling patterns

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

### Key Components

- **SharedDomainDelayManager**: Cross-process rate limiting
- **Worker Processes**: HTTP client + text processing only
- **Main Process**: Database operations + URL coordination
- **Result Queues**: Communication between processes
- **Graceful Shutdown**: Coordinated termination

## Performance

### Expected Performance:
- **Single-threaded**: ~1-3 requests/second
- **Multiprocessing (4 workers)**: ~4-12 requests/second
- **Scaling**: Nearly linear with worker count (up to network limits)

### Bottlenecks:
- **Human Behavior Simulation**: 0.5-2s per request (70% of time)
- **Device Verification**: 2-6s per protected site (20% of time)
- **Network Latency**: Variable based on connection

## Database Schema

### Tables Created:
- `urlsDB`: Successfully crawled URLs with content and scores
- `frontier`: Pending URLs for crawling
- `disallowed`: URLs blocked by robots.txt
- `errors`: Error logs with details

### Sample Query:
```sql
SELECT url, score, linking_depth 
FROM urlsDB 
WHERE score > 0.5 
ORDER BY score DESC 
LIMIT 10;
```

## Error Handling

The crawler includes comprehensive error handling:

- **HTTP Errors**: Timeout, connection, and status code errors
- **Content Errors**: Invalid HTML, insufficient content
- **Process Errors**: Worker crashes, communication failures
- **Database Errors**: Connection and query failures

All errors are logged to the database with detailed information.

## Testing

### Available Tests:
```bash
# Test basic multiprocessing functionality
python -m crawler.test_multiprocessing_simple

# Test graceful shutdown
python -m crawler.test_graceful_shutdown

# Test loop prevention (URL deduplication)
python -m crawler.test_loop_prevention

# Test proxy functionality
python -m crawler.test_proxy

# Test full multiprocessing suite
python -m crawler.test_multiprocessing
```

### Test Database:
Test runs create separate databases (e.g., `test_shutdown.db`) to avoid interfering with production data.

## Loop Prevention

The crawler has **robust loop prevention** to ensure it never visits pages that have already been crawled:

### **Multi-Layer Deduplication:**

1. **In-Memory Sets**: 
   - `visited_urls`: URLs currently being processed
   - `crawled_urls`: URLs successfully completed

2. **Database Persistence**: 
   - PRIMARY KEY constraint on URL column prevents duplicates
   - `is_url_crawled()` checks database for previously crawled URLs

3. **URL Filtering**: 
   - Extracts URLs from pages and filters out already-visited ones
   - Normalizes URLs (removes fragments, handles case sensitivity)

4. **Multiple Checkpoints**: 
   - Check during URL addition to frontier
   - Check during URL extraction from pages
   - Check during URL filtering

### **Cross-Session Persistence:**

The crawler maintains state across restarts:
- Previously crawled URLs are loaded from database
- Frontier URLs are restored from database
- No duplicate work is performed

### **Testing Loop Prevention:**

```bash
# Test that the crawler doesn't revisit crawled URLs
python -m crawler.test_loop_prevention
```

This test:
- Crawls URLs that link to each other
- Restarts the crawler and tries to add same URLs
- Verifies that duplicate URLs are rejected
- Confirms database persistence works correctly

## Safety and Ethics

This crawler is designed for **respectful web crawling**:

- **Rate Limiting**: Prevents server overload
- **Robots.txt**: Respects website crawling policies
- **Domain Delays**: Spreads requests across time
- **User-Agent**: Identifies itself properly
- **Error Handling**: Graceful failure without retry storms

## Troubleshooting

### Common Issues:

1. **"Cannot pickle DuckDB connection"**:
   - **Solution**: Use the updated multiprocessing implementation
   - **Cause**: Database connections can't be shared between processes

2. **Workers hanging during shutdown**:
   - **Solution**: The improved shutdown mechanism handles this
   - **Monitoring**: Watch for "Worker X: Finished gracefully" messages

3. **Lost results during shutdown**:
   - **Solution**: New implementation processes all results before stopping
   - **Verification**: Check final statistics for complete counts

4. **Performance not scaling**:
   - **Check**: Domain delays might be too high
   - **Adjust**: Reduce `domain_rotation_delay` for faster crawling

### Debug Mode:
```bash
# Enable verbose logging
python -m crawler.main --multiprocessing --max-workers 2 --debug
```

## Development

### Project Structure:
```
crawler/
├── main.py              # Entry point
├── crawler.py           # Main crawler class
├── multiprocessing_crawler.py  # Multiprocessing support
├── config.py            # Configuration management
├── database.py          # Database operations
├── http_client.py       # HTTP requests and anti-ban
├── text_processor.py    # Content extraction
├── scoring.py           # Relevance scoring
├── frontier.py          # URL queue management
├── url_manager.py       # URL validation and filtering
└── tests/               # Test files
```

### Adding New Features:
1. Update `config.py` for new configuration options
2. Modify worker function for processing changes
3. Update main crawler for coordination changes
4. Add tests for new functionality

## License

This project is designed for academic and research purposes at the University of Tübingen. 