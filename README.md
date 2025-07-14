# 🔍 Tübingen Search Engine

A modern semantic search engine focused on English-language content related to Tübingen, built with dense embeddings, vector search, and interactive visualization.

## 🌟 Project Overview

This project implements a complete search engine pipeline that crawls, indexes, and searches English-language content about Tübingen using state-of-the-art semantic search techniques.

### Key Features

- **🕷️ Web Crawling**: Focused crawling of Tübingen-related English content
- **🧠 Semantic Search**: Dense vector embeddings using Sentence Transformers
- **⚡ Vector Database**: DuckDB with native vector search and HNSW indexing
- **🎯 API-based Reranking**: OpenAI embedding API for fine-grained relevance scoring
- **🎨 Interactive UI**: D3.js-powered bubble visualization interface
- **🚀 RESTful API**: Flask-based search API with CORS support

## 🏗️ Architecture Overview

### Indexing Pipeline

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Crawler   │───▶│   DuckDB Store   │───▶│   Text Chunker  │
│                 │    │   (urlsDB)       │    │  (Sliding Win.) │
│ • Seed URLs     │    │                  │    │                 │
│ • Domain Focus  │    │ • URL + Metadata │    │ • 256 tokens    │
│ • Quality Score │    │ • Page Content   │    │ • 64 step size  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Vector Index  │◀───│   Text Embedder  │◀───│  Chunk Storage  │
│                 │    │                  │    │                 │
│ • DuckDB HNSW   │    │ • SentenceTransf │    │ • chunks_optim. │
│ • Vector Search │    │ • MiniLM-L6-v2   │    │ • embeddings    │
│ • Inner Product │    │ • 384 dimensions │    │ • chunk_id map  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Query Processing Pipeline

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Search Query   │───▶│  Query Embedding │───▶│  Vector Search  │
│                 │    │                  │    │                 │
│ • User Input    │    │ • Same Model     │    │ • DuckDB HNSW   │
│ • Text String   │    │ • 384-dim vector │    │ • Top-K chunks  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Search Results  │◀───│   API Reranker   │◀───│ Result Assembly │
│                 │    │                  │    │                 │
│ • Ranked Docs   │    │ • OpenAI Embed.  │    │ • Join Metadata │
│ • Similarity    │    │ • Sliding Window │    │ • Score Aggr.   │
│ • Metadata      │    │ • Fine-grained   │    │ • Deduplication │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🛠️ Technology Stack

### Core Components
- **Vector Database**: DuckDB with native vector search capabilities
- **Vector Indexing**: HNSW (Hierarchical Navigable Small Worlds) algorithm  
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2)
- **Web Framework**: Flask with CORS support
- **Frontend**: Vanilla JavaScript + D3.js

### Dependencies
- `sentence-transformers>=5.0.0` - Dense text embeddings
- `duckdb==1.3.1` - Analytical database with vector search support
- `flask>=2.3.0` - Web API framework
- `openai` - API client for reranking embeddings
- `numpy>=2.3.1` - Numerical computations
- `scikit-learn==1.7.0` - ML utilities


## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd Modern-Search-Engines-Project

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Search Engine

#### Option A: Command Line Interface
```bash
python main.py
```

#### Option B: Web API + Interactive UI
```bash
python search_api.py
```
Then open `http://localhost:5000` in your browser.

### 3. Usage Examples

**Command Line:**
```bash
>> university research tübingen
>> historical old town
>> neckar river activities
```

**API Request:**
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "university research", "top_k": 10}'
```

## 📁 Project Structure

### Core Search Engine
```
├── main.py                 # CLI search interface
├── search_api.py           # Flask web API  
├── retriever.py            # Main search logic
├── config.py               # Configuration settings
└── requirements.txt        # Python dependencies
```

### Indexing System
```
indexer/
├── indexer.py              # Document indexing orchestrator
├── embedder.py             # Text embedding & vector storage
└── bm25.py                 # BM25 scoring (optional)
```

### Web Interface
```
templates/
└── index.html              # Search interface with D3.js
static/
├── style.css               # UI styling
└── main.js                 # Interactive visualization
```

### Crawling Infrastructure
```
MaxPart/crawler/
├── seed.py                 # Seed URL definitions
├── metric.py               # Page quality scoring
├── UTEMA.py               # Main crawler logic
└── CrawlerHelpers.py       # Utility functions
```

### Optional Reranker
```
reranker/
├── reranker_api.py         # API-based reranking service
├── config.yaml             # Reranker configuration
└── README.md               # Detailed reranker docs
```

### Research Components (Demos)
```
query_processing/           # Alternative ranking models
├── models/
│   ├── bm25.py            # BM25 implementation
│   ├── tfidf.py           # TF-IDF scoring
│   ├── bi_encoder.py      # Dense retrieval
│   └── pointwise_ltr.py   # Learning-to-rank
└── demo_*.py              # Model demonstrations
```

## ⚙️ Configuration

Key settings in `config.py`:

```python
# Embedding Configuration
EMBEDDING_MODEL = "all-MiniLM-L6-v2"    # Sentence transformer model
EMBEDDING_DIMENSION = 384                # Vector dimension

# Database Settings  
DB_PATH = "index/crawlerDB.duckdb"       # Main database location
DB_TABLE = "urlsDB"                      # Document table name

# Processing Parameters
DEFAULT_BATCH_SIZE = 32                  # Document processing batch
DEFAULT_EMBEDDING_BATCH_SIZE = 64        # Embedding batch size
DEFAULT_WINDOW_SIZE = 256                # Text chunk size (tokens)
DEFAULT_STEP_SIZE = 64                   # Sliding window step

# Search Settings
MAX_CANDIDATES = 1000                    # Vector search candidates
USE_BM25 = False                         # Enable BM25 fallback
```

## 🎯 Search Process Details

### 1. Document Indexing
1. **Text Chunking**: Documents split into overlapping 256-token windows
2. **Embedding Generation**: Each chunk encoded to 384-dimensional vectors  
3. **Vector Storage**: Embeddings stored in DuckDB with HNSW indexing
4. **Metadata Linking**: Chunks linked to source documents and URLs

### 2. Query Processing
1. **Query Embedding**: User query encoded with same transformer model
2. **Vector Search**: DuckDB HNSW index finds most similar document chunks
3. **Score Aggregation**: Chunk scores aggregated by document
4. **Result Ranking**: Documents ranked by maximum chunk similarity
5. **Metadata Enrichment**: Results enhanced with titles, URLs, snippets

### 3. API-based Reranking
1. **Candidate Selection**: Top-K documents from initial search
2. **Fine-grained Analysis**: Sliding window reanalysis of full documents  
3. **API Embeddings**: OpenAI embedding API for enhanced similarity computation
4. **Final Ranking**: Improved relevance ordering based on API embeddings

## 🎨 Interactive Features

### Bubble Visualization
- **Dynamic Sizing**: Bubble size reflects relevance score
- **Color Coding**: Different colors for various content domains
- **Interactive**: Click bubbles to view full document details
- **Real-time**: Updates dynamically with new searches

### Search Interface
- **Autocomplete**: Smart query suggestions
- **Real-time Results**: Instant search as you type
- **Faceted Navigation**: Filter by content type, domain, date
- **Export Options**: Download results in various formats

## 📊 Performance Characteristics

### Search Speed
- **Cold Start**: ~2-3 seconds (first query after startup)
- **Warm Queries**: ~100-500ms (cached embeddings)
- **Batch Processing**: 10-100x faster with optimized batching

### Accuracy Metrics
- **Semantic Understanding**: Handles synonyms and context
- **Multilingual Robustness**: Works with mixed German/English content
- **Domain Specificity**: Optimized for Tübingen-related queries

### Scalability
- **Document Capacity**: Efficiently handles 10K+ documents
- **Memory Usage**: ~2GB RAM for full index in memory
- **GPU Acceleration**: Optional CUDA support for larger datasets

## 🔧 Advanced Usage

### Custom Embedding Models
```python
# In config.py, change the model:
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### Batch Processing
```python
# Process multiple documents efficiently
indexer_instance.index_documents(
    batch_size=64,
    embedding_batch_size=128,
    force_reindex=False
)
```

### API Integration
```python
import requests

response = requests.post('http://localhost:5000/api/search', json={
    'query': 'machine learning research',
    'top_k': 5,
    'include_snippets': True
})
results = response.json()
```
