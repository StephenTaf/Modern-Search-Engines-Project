# Document Reranker API

A FastAPI-based web service that reranks text documents based on semantic similarity to a query using sliding window embeddings. The API works with a JSON database of documents and processes them by document IDs with **optimized batched embeddings** for maximum efficiency.

## ⚡ Key Features

- 🔥 **Optimized Batched Embeddings**: Dramatically reduces API calls with true batching (10-100x fewer requests)
- 📊 **Database-Driven**: Load documents from JSON database with fast doc_id indexing
- 🎯 **Sliding Window Processing**: Configurable window size and step for optimal context preservation
- 🚀 **Parallel Processing**: Concurrent API calls with rate limiting for maximum throughput
- 🔧 **Flexible Configuration**: Comprehensive YAML-based settings
- 📈 **Multiple API Providers**: Support for OpenAI, Together.xyz, and other compatible APIs
- 🛡️ **Rate Limiting**: Built-in RPM control to prevent API quota exhaustion
- 📋 **Database Management**: Full CRUD operations for document management
- 📊 **Monitoring & Health**: Detailed logging and status endpoints

## 🚀 Performance Optimizations

### Batched Embeddings
Our **revolutionary batched embedding system** provides massive efficiency gains:

- **Before**: 100 text windows = 100 API calls
- **After**: 100 text windows = 1 API call (with batch_size=100)
- **Result**: **Up to 100x fewer API calls!** 🔥

### Parallel Processing
- Multiple batches process simultaneously after rate limit approval
- `asyncio.gather()` ensures optimal network utilization
- Smart rate limiting prevents quota violations

### Example Performance Impact
```
Scenario: 500 text windows, batch_size=100
├── Old Approach: 500 API calls × 200ms = 100 seconds
└── New Approach: 5 batched calls in parallel = ~2 seconds
    
Result: 50x faster processing! ⚡
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Document Database

Create a `documents.json` file with your document data. The file should contain a list of dictionaries with the following fields:

```json
[
    {
        "doc_id": "doc_001",
        "title": "Document Title",
        "url": "https://example.com/document",
        "text": "Full document text content...",
        "similarity": 0.85
    }
]
```

**Required fields:**
- `doc_id`: Unique identifier (string or integer)
- `title`: Document title
- `url`: Source URL or reference
- `text`: Full document text content
- `similarity`: Original retrieval similarity score

### 3. Configure the API

Edit the `config.yaml` file to set your preferences:

```yaml
# Essential configuration
openai:
  api_key: "your-api-key-here"
  embedding_model: "BAAI/bge-large-en-v1.5"
  batch_size: 100  # Higher values = fewer API calls (up to provider limits)
  base_url: "https://api.together.xyz/v1"  # Optional: for alternative providers

database:
  data_path: "documents.json"  # Path to your JSON database

sliding_window:
  default_window_size: 500
  default_step_size: 400
  default_top_n: 10

server:
  host: "0.0.0.0"
  port: 8000

rate_limiting:
  enabled: true
  requests_per_minute: 2400  # With batching, actual requests are much fewer
```

**Important**: 
- Set your actual API key in the config file
- Higher `batch_size` = fewer API calls and better efficiency
- Rate limiting works with the batched approach for optimal performance

### 4. Run the Server

```bash
python reranker_api.py
```

The server will start on the configured host and port (default: `http://localhost:8000`)

## API Usage

### Main Endpoint: `/rerank`

**POST** request to rank documents based on query similarity with **batched processing**.

#### Request Parameters:

```json
{
  "doc_ids": ["doc_001", "doc_002", "doc_003"],
  "query": "your search query",
  "window_size": 500,     // optional, uses config default
  "step_size": 400,       // optional, uses config default
  "top_n": 10            // optional, uses config default
}
```

#### Response:

```json
{
  "document_scores": [
    {
      "doc_id": "doc_002",
      "title": "Document Title",
      "url": "https://example.com/doc",
      "similarity_score": 0.91,
      "original_similarity": 0.85
    }
  ],
  "top_windows": [
    {
      "text": "Most relevant text window content...",
      "similarity_score": 0.93,
      "doc_id": "doc_002",
      "title": "Document Title",
      "window_index": 3
    }
  ],
  "total_documents": 3,
  "total_windows": 45
}
```

### Example Usage with curl:

```bash
curl -X POST "http://localhost:8000/rerank" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_ids": ["doc_001", "doc_002", "doc_003"],
    "query": "machine learning algorithms",
    "window_size": 500,
    "step_size": 400,
    "top_n": 5
  }'
```

### Example Usage with Python:

```python
import requests

response = requests.post("http://localhost:8000/rerank", json={
    "doc_ids": ["doc_001", "doc_002", "doc_003"],
    "query": "machine learning algorithms",
    "window_size": 500,
    "step_size": 400,
    "top_n": 5
})

result = response.json()
print("Document Rankings:")
for doc in result["document_scores"]:
    print(f"{doc['doc_id']}: {doc['similarity_score']:.3f} (original: {doc['original_similarity']:.3f})")

print("\nTop Windows:")
for window in result["top_windows"]:
    print(f"{window['doc_id']} (window {window['window_index']}): {window['similarity_score']:.3f}")
    print(f"Text: {window['text'][:100]}...")
```

## Database Management Endpoints

### Get Database Info: `/database/info`
**GET** request to view database statistics:

```bash
curl http://localhost:8000/database/info
```

### Get All Doc IDs: `/database/doc-ids`
**GET** request to list all available document IDs:

```bash
curl http://localhost:8000/database/doc-ids
```

### Get Document by ID: `/database/documents/{doc_id}`
**GET** request to retrieve specific document:

```bash
curl http://localhost:8000/database/documents/doc_001
```

### Reload Database: `/database/reload`
**POST** request to reload database from file:

```bash
curl -X POST http://localhost:8000/database/reload
```

## Other Endpoints

### Health Check: `/health`
**GET** request to check service status and view current configuration:

```bash
curl http://localhost:8000/health
```

### Rate Limit Status: `/rate-limit-status`
**GET** request to view current API usage and efficiency metrics:

```bash
curl http://localhost:8000/rate-limit-status
```

### Configuration: `/config`
**GET** request to view current configuration (with sensitive data hidden):

```bash
curl http://localhost:8000/config
```

### API Documentation: `/docs`
**GET** request to view the interactive Swagger documentation.

## Configuration Options

The `config.yaml` file provides comprehensive configuration:

### Database Settings
- `data_path`: Path to JSON file containing documents

### OpenAI Settings
- `api_key`: Your API key
- `embedding_model`: Embedding model to use
- `batch_size`: Number of texts to process per API call (higher = more efficient)
- `base_url`: Optional custom API endpoint

### Rate Limiting
- `enabled`: Enable/disable rate limiting
- `requests_per_minute`: Maximum API requests per minute (batching reduces actual calls)

### Sliding Window Settings
- `default_window_size`: Default number of tokens per window
- `default_step_size`: Default step size for sliding windows
- `default_top_n`: Default number of top windows to return

## 🔧 How It Works

1. **Configuration Loading**: Loads settings from `config.yaml` at startup
2. **Database Loading**: Loads and indexes documents from JSON file by doc_id
3. **Document Retrieval**: Looks up documents by provided doc_ids
4. **Tokenization**: Uses HuggingFace tokenizer (without special tokens initially)
5. **Sliding Windows**: Creates overlapping windows preserving context
6. **Window Collection**: Aggregates all windows from all documents
7. **🚀 Batched Embedding**: Processes all windows in optimized batches via `process_windows_batched()`
   - Groups windows into batches (configurable size)
   - Makes parallel API calls with rate limiting
   - Preserves order using `asyncio.gather()`
8. **Query Processing**: Embeds the search query
9. **Similarity Calculation**: Computes cosine similarity between query and all windows
10. **Document Scoring**: Takes maximum similarity score across all windows per document
11. **Ranking**: Returns documents sorted by similarity score and top-N windows

## Database Format

The JSON database file should contain a list of document records:

```json
[
    {
        "doc_id": "unique_identifier",  // Can be string or integer
        "title": "Document Title", 
        "url": "https://source.url",
        "text": "Full document content...",
        "similarity": 0.85
    }
]
```

Multiple documents can share the same `doc_id` (useful for document chunks or sections).

## 📊 Performance Notes

### Efficiency Gains
- **🔥 Batched embeddings**: 10-100x fewer API calls
- **⚡ Parallel processing**: Multiple batches run simultaneously
- **💰 Cost reduction**: Fewer billable API requests
- **🎯 Rate limit optimization**: Better quota utilization
- **📈 Higher throughput**: Process more documents faster

### Optimization Tips
- **Increase `batch_size`**: Higher values = fewer API calls (limited by provider)
- **Tune window settings**: Balance context vs. processing speed
- **Monitor rate limits**: Use `/rate-limit-status` endpoint
- **Database indexing**: In-memory indexing provides fast doc_id lookups

### Performance Factors
- **Batch size**: Higher = more efficient API usage
- **Window count**: More windows = longer processing (but better accuracy)
- **Network latency**: Batching reduces impact significantly
- **API provider**: Different providers have different batch limits

## Requirements

- Python 3.8+
- API key for embedding service (OpenAI, Together.xyz, etc.)
- Valid JSON database file with document records
- Valid `config.yaml` file with required settings
- Internet connection for API calls

## 🐛 Troubleshooting

### Common Issues

1. **Database file not found**: Ensure JSON file exists and path is correct in config
2. **Invalid JSON format**: Validate your JSON database file structure
3. **Missing doc_ids**: Check that requested doc_ids exist in the database
4. **API errors**: Verify your API key and rate limits
5. **Configuration errors**: Ensure `config.yaml` has all required fields
6. **Memory issues**: Reduce batch size and window size for large databases
7. **Type errors**: Ensure doc_id consistency (API handles both strings and integers)

### Performance Troubleshooting

1. **Check batch efficiency**: Monitor logs for "X texts in 1 API call" messages
2. **Rate limit status**: Use `/rate-limit-status` to check API usage
3. **Adjust batch size**: Increase for better efficiency (up to provider limits)
4. **Monitor parallel calls**: Check logs for concurrent batch processing

## 🎯 Development Features

### VS Code Integration
- `.vscode/launch.json`: Multiple debug configurations
- `.vscode/settings.json`: Python formatting and linting
- `.vscode/tasks.json`: Development tasks

### Testing and Debugging
- `debug_server.py`: Comprehensive server diagnostic tool
- `example_api_calls.py`: API client examples and testing
- Health checks and monitoring endpoints

This API provides **enterprise-grade performance** with dramatic efficiency improvements through batched processing! 🚀 
