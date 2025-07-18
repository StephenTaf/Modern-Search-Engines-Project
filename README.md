# Tübingen Search Engine

A semantic search engine for English-language content about Tübingen, built with modern NLP techniques and interactive visualization.

## What is this?

This project is our coursework submission for the Modern Search Engines course at the University of Tübingen to build a comprehensive search engine that demonstrates key concepts from information retrieval and modern NLP. We've built a complete pipeline that crawls the web for Tübingen-related content, processes it intelligently, and provides fast semantic search with an interactive interface.


## Key Features

- **Web Crawling**: Discovers and crawls English content about Tübingen starting from manually curated seed
- **Semantic Search**: Uses neural embeddings to understand query intent and context
- **Fast Vector Search**: DuckDB with HNSW indexing for fast retrieval
- **Interactive Visualization**: D3.js bubble interface for exploring search results
- **Data Processing Pipeline**: Handles duplicate detection, language filtering, and content preprocessing
- **Reranking**: Advanced fine-tuning of search results using OpenAI embeddings via sliding window analysis

## How It Works

### The Big Picture

```
Web Content → Crawler → Data Processing → Indexing → Search Interface
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
- Splits documents into overlapping chunks (256 tokens with 200-token steps)
- Generates 384-dimensional embeddings using Sentence Transformers
- Stores vectors in DuckDB with HNSW indexing for fast retrieval

**4. Search & Ranking**
- Embeds user queries using the same model
- Performs approximate nearest neighbor search
- Aggregates chunk scores by document
- Reranks results using OpenAI's embedding API with sliding window analysis for superior relevance

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
│       └── bm25.py           # Traditional BM25 scoring (optional)
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
└── Data Storage
    ├── crawlerDb.duckdb      # Main document database
    ├── crawler_v*.db         # Crawling session databases
```

## Getting Started


### Installation

```bash
git clone https://github.com/StephenTaf/Modern-Search-Engines-Project.git
cd Modern-Search-Engines-Project
pip install -r requirements.txt
```

### Quick Start

**Prerequisites: Start the Reranker Service**
```bash
# First, configure your OpenAI API key in reranker/config.yaml
cd reranker/
python reranker_api.py
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

# Then index all documents
python index_all.py

# Start the reranker service
cd reranker/
python reranker_api.py

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

```



## Configuration

Key settings in `config.py`:

```python
# Embedding model and dimensions
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Sentence transformer model
EMBEDDING_DIMENSION = 384             # Vector dimension

# Database paths
DB_PATH = "crawlerDb.duckdb"          # Main database
DB_TABLE = "urlsDB"                   # Document table

# Processing parameters
DEFAULT_WINDOW_SIZE = 256             # Text chunk size (tokens)
DEFAULT_STEP_SIZE = 200               # Sliding window step
DEFAULT_EMBEDDING_BATCH_SIZE = 64     # Embedding batch size

# Search settings
TOP_K_RETRIEVAL = 200                 # Initial retrieval count
MAX_CANDIDATES = 1000                 # Maximum chunks to fetch using ANN

# Reranking settings
RERANKER_API_URL = "http://localhost:8000"  # Reranker service URL
RERANKER_TIMEOUT = 100                # Timeout for reranker API requests
```

## Technical Details

### Text Processing
- **Chunking**: Overlapping windows to preserve context across boundaries
- **Language Detection**: Filters for English content using langdetect and polyglot
- **Deduplication**: URL normalization to remove duplicate pages


### Vector Search & Reranking
- **Initial Retrieval**: all-MiniLM-L6-v2 (384 dimensions, good balance of speed/quality)
- **Index**: DuckDB's native HNSW implementation  
- **Similarity**: Cosine similarity for semantic matching
- **Aggregation**: Max-pooling of chunk scores by document
- **Reranking**: BAAI/bge-large-en-v1.5 via OpenAI API with sliding window analysis (500-token windows, 400-token step)
- **Optimization**: Batched embeddings reduce API calls by up to 100x

### Performance
- **Search Speed**: < 1min for typical queries
- **Index Size**: TBD 
- **Memory Usage**: TBD
- **Scalability**: Tested with 100K+ documents, can handle much more

## Architecture Components

### Two-Stage Ranking System
Our search engine implements a sophisticated two-stage ranking approach:

1. **Initial Retrieval**: Fast vector search using all-MiniLM-L6-v2 embeddings in DuckDB
2. **Reranking**: Advanced semantic analysis using BAAI/bge-large-en-v1.5 via OpenAI API

### Reranking Service 
The reranking service provides significant quality improvements:

- **Sliding Window Analysis**: Processes documents in 500-token windows with 400-token steps
- **Batched Embeddings**: Reduces API calls by 10-100x through batching
- **Enhanced Model**: Uses BAAI/bge-large-en-v1.5 for more nuanced semantic understanding
- **FastAPI Service**: Runs as a separate service on port 8000

To start the reranking service:
```bash
cd reranker/
python reranker_api.py
```

### BM25 Fallback
While the system primarily uses neural embeddings, you can enable traditional BM25 scoring:

```python
# In config.py
USE_BM25 = True
```



*Built for the Modern Search Engines course at the University of Tübingen*
