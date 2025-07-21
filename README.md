# Tübingen Search Engine

A semantic search engine for English-language content about Tübingen, built with modern NLP techniques and interactive visualization.

## What is this?

This project is our coursework submission for the Modern Search Engines course at the University of Tübingen to build a comprehensive search engine that demonstrates key concepts from information retrieval and modern NLP. We've built a complete pipeline that crawls the web for Tübingen-related content, processes it intelligently, and provides fast semantic search with an interactive interface.


## Key Features

- **Web Crawling**: Discovers and crawls English content about Tübingen starting from manually curated seed
- **Lexical Search**: Uses BM25 scores to quickly filter the most relevant documents
- **Semantic Search**: Reranks the results from BM25 retrieval with neural embeddings for better search ranking
- **Interactive Visualization**: D3.js bubble interface for exploring search results
- **Search Overview**: Uses an LLM to generate a structures response based on top results

## How It Works

### The Big Picture

```
Web Content -> Crawler -> Data Processing -> Indexing -> Search Interface
```

### Detailed Pipeline

**1. Web Crawling**
- Starts with seed URLs for Tübingen-related sites (university, government, tourism)
- Crawls systematically while respecting robots.txt and rate limits
- Parses HTML to better filter relevant contents from the page

**2. Data Processing** 
- Removes duplicates using URL normalization
- Detects and filters content by language
- Merges data from multiple crawling sessions/users
- Preprocesses text for optimal indexing

**3. Indexing**
- Stores two complementary indexes for hybrid search:
  - **BM25 Index**: Traditional lexical search index for fast keyword-based retrieval
  - **Neural Index**: Uses sliding window approach - splits documents into overlapping chunks (512 tokens with 450-token steps)
- Generates 768-dimensional embeddings using Sentence Transformers 
- Stores BM25 stats as well as embedding vectors in DuckDB for persistence and fast retrieval

**4. Search & Ranking**
- Uses a two-stage hybrid approach for optimal relevance:
  - **Stage 1**: BM25 lexical search retrieves initial candidate documents
  - **Stage 2**: Neural reranking using locally stored embeddings (generated during indexing with Sentence Transformers)
- Embeds user queries and computes similarity against pre-computed document chunk embeddings stored in DuckDB
- Aggregates chunk scores by document using max-pooling
- Final ranking combines lexical and semantic signals for superior relevance

## Project Structure

```
Modern-Search-Engines-Project/
│
├── Core Search Engine
│   ├── search_api.py          # Flask web API and main interface
│   ├── retriever.py           # Search logic and result ranking
│   ├── index_all.py           # Bulk indexing script
│   └── config.py              # Configuration settings
│
├── Indexing System
│   └── indexer/
│       ├── indexer.py         # Document processing and storage
│       ├── embedder.py        # Text embedding generation
│       └── bm25_indexer.py    # BM25 indexing and scoring
│
├── Data Processing
│   ├── preprocessor.ipynb     # Data cleaning and merging
│   └── Group Project Rules.ipynb  # Project guidelines
│
├── Web Crawling
│   └── MaxPart/crawler/
│       ├── UTEMA.py          # Main crawler implementation
│       ├── seed.py           # Seed URL definitions
│       ├── metric.py         # Page quality scoring
│       └── CrawlerHelpers.py # Utility functions
│
├── User Interface
│   ├── templates/index.html   # Search interface
│   └── static/
│       ├── style.css         # UI styling
│       └── main.js           # Interactive visualization
│
├── Reranking Service
│   └── reranker/
│       ├── reranker_api.py   # FastAPI reranking service 
│       ├── config.yaml       # Reranker configuration
│       └── README.md         # Detailed reranking documentation
│
├── Search Assistant
│   └── search_assistant/
│       └── main.py           # LLM-powered summarisation
│
└── Data Storage
    ├── crawlerDb.db          # Main document database
    ├── crawler_v*.db         # Crawling session databases
```

## Getting Started

### Prerequisites

**Required Dataset**
You need a crawled dataset stored in a DuckDB file named `crawlerDB.db` (default). This file should contain a `urlsDB` table with at least the following fields:
- `id` - Unique document identifier
- `url` - Source URL of the document
- `title` - Document title
- `text` - Document content

The database filename and path can be configured in:
- `config.py` (DB_PATH variable)
- `reranker/config.yaml` (database configuration)

 The dataset can also be downloaded at https://huggingface.co/datasets/lalit3c/Tuebingen-Crawled/tree/main 

### Installation

```bash
git clone https://github.com/StephenTaf/Modern-Search-Engines-Project.git
cd Modern-Search-Engines-Project
pip install -r requirements.txt
```

### Quick Start

**Prerequisites: Start Required Services**
```bash
# Start Reranker service API
cd reranker/
python reranker_api.py

# Start the search assistant LLM service
# configure your Cerebras API key in search_assistant/config.yaml. To get a free API key, sign up here: https://www.cerebras.ai/inference
cd search_assistant/
python main.py  

```

**Option 1: Web Interface (Recommended)**
```bash
# In a new terminal
python search_api.py
```
Then open http://localhost:5000 in your browser.

**Option 2: Build Your Own Index**
```bash
# First, run the data preprocessing if you have multiple raw crawl data (optional)
jupyter notebook preprocessor.ipynb

# Then index all documents (BM25 + sentence transformers embeddings)
python index_all.py

# Start the reranker service
cd reranker/
python reranker_api.py

# Start LLM Summarization service
cd search_assistant/
python main.py

# Finally, start the search API (in a new terminal)
python search_api.py
```

## Usage

### Web Interface
The bubble visualization shows search results as interactive circles:
- **Bubble size** = relevance score
- **Colors** = different content types/domains
- **Click** = visit the original page
- **Drag** = pan around the visualization
- **Scroll** = zoom in/out

### API Usage

**Single Query Search**
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "university research tübingen", "top_k": 10}'
```

**Response Format:**
```json
{
  "llm_response": "Generated response based on the most relevant content windows",
  "documents": [
    {
      "query_id": "unique-query-id",
      "rank": 1,
      "url": "https://example.com",
      "score": 0.95,
      "title": "Document Title",
      "snippet": "Document snippet...",
      "domain": "domain-topic",
      "doc_id": "document-id",
    }
  ]
}
```

The API response includes:
- **llm_response**: LLM-generated response based on the most relevant content windows from the search results
- **documents**:  search results with document metadata

**Batch Query Processing**

The search engine supports efficient batch processing of multiple queries with parallel execution:

1. **Prepare queries file**: Create a `queries.txt` file in the project root with the format:
   ```
   query_num<tab>query_text
   ```
   Example:
   ```
   1	university research tübingen
   2	student life tübingen
   3	computer science courses
   ```

2. **Process batch queries** (returns JSON response):
   ```bash
   curl -X POST http://localhost:5000/api/batch_search
   ```

3. **Process and save to file** (saves results to `batch_search_results.txt`):
   ```bash
   curl -X POST http://localhost:5000/api/batch_search_file
   ```

**Batch Processing Features:**
- **Parallel Execution**: All queries processed simultaneously using asyncio.gather
- **Error Handling**: Individual query failures don't stop batch processing
- **File Output**: Results saved in format: `query_num<tab>rank<tab>url<tab>score`

## Configuration

Key settings in `config.py`:

```python
# Embedding model and dimensions
EMBEDDING_MODEL = "as-bessonov/reranker_searchengines_cos2"  # Sentence transformer model, self trained
EMBEDDING_DIMENSION = 768            # Vector dimension

# Database paths
DB_PATH = "crawlerDb_sbert.duckdb"          # Main database
DB_TABLE = "urlsDB"                   # Document table

# Processing parameters
DEFAULT_WINDOW_SIZE = 512             # Text chunk size (tokens)
DEFAULT_STEP_SIZE = 450               # Sliding window step
DEFAULT_EMBEDDING_BATCH_SIZE = 64     # Embedding batch size

# Search settings
TOP_K_RETRIEVAL = 1000                 # Initial retrieval count from BM25


# Reranking settings
RERANKER_API_URL = "http://localhost:8000"  # Reranker service URL
RERANKER_TIMEOUT = 100                # Timeout for reranker API requests

# LLM Assistant settings
LLM_API_URL = "http://localhost:1984"     # Search assistant (LLM Summarization) API URL
LLM_TIMEOUT = 30                           # Timeout for LLM API requests
LLM_MAX_WINDOWS = 10                        # Maximum content windows to pass to LLM processing
```

## Technical Details

### Text Processing
- **Chunking**: Overlapping windows (512 tokens with 450-token steps) to preserve context across boundaries
- **Language Detection**: Filters for English content using langdetect and polyglot
- **Deduplication**: URL normalization to remove duplicate pages

### Hybrid Search & Reranking
- **Initial Retrieval**: BM25 lexical search for fast keyword-based document retrieval
- **Embeddings**: 768-dimensional vectors using self trained model, stored in DuckDB
- **Similarity**: Cosine similarity for semantic matching between query and document chunks
- **Aggregation**: Max-pooling of chunk scores by document
- **Reranking**: Uses locally stored embeddings from indexing process for semantic reranking
- **Storage**: DuckDB with efficient vector operations for fast retrieval

### Performance
- **Search Speed**: < 30 seconds for typical queries
- **Index Size**: ~7GB (incl. vector embeddings) 
- **Scalability**: Tested with 100K+ documents, can handle much more

## Architecture Components

### Two-Stage Ranking System
Our search engine implements a two-stage ranking approach:

1. **Initial Retrieval**: Fast BM25 lexical search to retrieve candidate documents
2. **Neural Reranking**: Semantic analysis using locally stored embeddings in DuckDB

### Reranking Service 
The reranking service provides significant quality improvements:

- **Local Embeddings**: Uses pre-computed embeddings stored in DuckDB from the indexing process
- **Sliding Window Analysis**: Processes documents in overlapping chunks for comprehensive coverage
- **FastAPI Service**: Runs as a separate service on port 8000

To start the reranking service:
```bash
cd reranker/
python reranker_api.py
```


*Built for the Modern Search Engines course at the University of Tübingen*
