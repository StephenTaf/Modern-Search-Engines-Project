# Indexer Module

The indexer module is responsible for processing and indexing documents from the crawled data to enable efficient search and retrieval. It provides both semantic search capabilities using text embeddings and traditional keyword-based search through BM25 scoring.

## Overview

This module processes documents from a DuckDB database, generates embeddings for text chunks using sliding window approach, and stores them in an optimized database structure for fast retrieval. The system implements a hybrid architecture combining BM25 lexical matching with dense vector embeddings for comprehensive search capabilities.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INDEXING PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Raw Crawled    │    │  Preprocessing  │    │   Text Chunking │    │   Embedding     │    │  Vector Storage │
│  Data (Multi-   │───▶│  (Language +    │───▶│   (Sliding      │───▶│   Generation    │───▶│   (Sequential)  │
│  Source)        │    │  Deduplication) │    │   Window)       │    │ (for Reranker)  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │                       │
         │                       │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ • Multiple DBs  │    │ • URL Normalize │    │ • Window Size:  │    │ • Model:        │    │ • Sequential    │
│ • Document ID   │    │ • Duplicate     │    │   512 tokens    │    │   self          │    │   Similarity    │
│ • Title         │    │   Removal       │    │ • Step Size:    │    │   trained model │    │ • Database      │
│ • Full Text     │    │ • Language      │    │   450 tokens    │    │ • Dimension:    │    │   Storage       │
│ • URL           │    │   Detection     │    │ • Overlap: 62   │    │   768           │    │ • Normalized    │
│ • Mixed Lang    │    │ • English Only  │    │   tokens (12%)  │    │ • Normalized    │    │   Vectors       │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE LAYER                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   
│ Raw Data (Multi)│    │ chunks_optimized│    │   embeddings    │    │   BM25 Tables   │   
│                 │    │                 │    │                 │    │                 │ 
│ • crawler_v4.db │    │ • chunk_id      │    │ • chunk_id      │    │ • doc_stats     │ 
│ • crawlerDb.db  │───▶│ • doc_id        │───▶│ • embedding     │───▶│ • term_freq     │
│ • Others        │    │ • chunk_text    │    │   [768 dims]    │    │ • term_stats    │   
│                 │    │                 │    │                 │    │ • corpus_stats  │    
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    
```

## Configuration

The indexer uses configuration parameters from `config.py`:

### Vector Embeddings Configuration
- **EMBEDDING_MODEL**: `"as-bessonov/reranker_searchengines_cos2"` - Self-trained model to get embeddings
- **EMBEDDING_DIMENSION**: `768` - Dimension of the embedding vectors
- **DEFAULT_WINDOW_SIZE**: `512` - Window size for text chunking (tokens)
- **DEFAULT_STEP_SIZE**: `450` - Step size for sliding window chunking (tokens)
- **OVERLAP_SIZE**: `62` - Token overlap between chunks (12% overlap)
- **DEFAULT_EMBEDDING_BATCH_SIZE**: `64` - Batch size for generating embeddings
- **DEFAULT_DB_FETCH_BATCH_SIZE**: `256` - Batch size for fetching documents from database

### BM25 Configuration
- **BM25_BATCH_SIZE**: `5000` - Batch size for BM25 processing
- **PARALLEL_THRESHOLD**: `50` - Minimum documents for parallel processing

### Database Configuration
- **DB_PATH**: `"crawlerDB.duckdb"` - Path to the DuckDB database
- **DB_TABLE**: `"urlsDB"` - Table name containing the crawled documents


## Components

### Preprocessing Pipeline (`preprocessor.ipynb`)

The preprocessing pipeline implements a robust multi-session data integration system with comprehensive quality control.

**Advanced Features:**
- **Multi-Session Integration**: Handles data from multiple crawling sessions across different databases
- **Aggressive URL Normalization**: Removes protocols, query parameters, and trailing slashes for maximum duplicate detection
- **Dual-Phase Deduplication**: Cross-dataset and internal deduplication for data integrity
- **Language Detection**: Dual-library approach with lenient 15% confidence threshold

**Processing Pipeline:**

1. **Data Integration**:
   - Connects to multiple DuckDB databases (`crawlerDb.duckdb`, `crawler_v*.db`)
   - Merges datasets while preserving data lineage
   - Handles schema variations across data sources

2. **URL Normalization Strategy**:
   ```
   https://www.example.com/path?param=value/ 
   -> www.example.com/path
   ```
   - Maximizes duplicate detection accuracy
   - Preserves original URLs for reference

3. **Dual-Phase Duplicate Removal**:
   - **Phase 1**: Filter URLs existing in historical data
   - **Phase 2**: Remove duplicates within new dataset
   - Ensures both historical consistency and internal integrity

4. **Language Detection System**:
   - Uses both `langdetect` and `polyglot` libraries
   - Accepts content if either library detects English ≥15% confidence
   - Lenient threshold to avoid potentially excluding English language content

5. **Data Standardization**:
   - Sequential ID assignment for new documents


**Dependencies:**
- `duckdb`: Database operations
- `pandas`: Data manipulation with `swifter` for parallel processing
- `langdetect`: Primary language detection
- `polyglot`: Secondary language detection with confidence scores

### BM25 Indexing System (`bm25_indexer.py`)

Implements a scalable, normalized BM25 system with database persistence and advanced text processing.

**Architecture Features:**
- **Normalized Four-Table Schema**: Separates concerns for efficient updates and queries
- **Advanced Text Processing**: spaCy-based lemmatization and intelligent filtering
- **Adaptive Batch Processing**: Scales from single-threaded to parallel processing
- **Incremental Indexing**: Processes only new documents while updating global statistics

**Database Schema:**
```sql
-- Document metadata
CREATE TABLE bm25_doc_stats(
    doc_id BIGINT PRIMARY KEY,
    doc_length INTEGER,
    processing_timestamp TIMESTAMP
);

-- Term frequencies per document
CREATE TABLE bm25_term_freq(
    doc_id BIGINT,
    term TEXT,
    frequency INTEGER,
    PRIMARY KEY (doc_id, term)
);

-- Global term statistics
CREATE TABLE bm25_term_stats(
    term TEXT PRIMARY KEY,
    document_frequency INTEGER,
    total_frequency INTEGER,
    idf_score REAL
);

-- Corpus-level metrics
CREATE TABLE bm25_corpus_stats(
    average_document_length REAL,
    total_documents INTEGER
);
```

**Text Processing Pipeline:**
1. **Content Combination**: Title + body text for comprehensive indexing
2. **Unicode Normalization**: Change all spelling variations of 'Tübingen' to a standard form
3. **spaCy Processing**: Lemmatization, stop word removal, linguistic filtering
4. **Length Management**: 1M character limit for compatibility

**Performance Optimizations:**
- Precomputed IDF scores eliminate runtime calculations
- Strategic database indexing on lookup columns
- Bulk operations with optimized transactions
- CPU-core-based worker scaling for parallel processing

### Dense Vector Indexing System

Implements an advanced sliding window approach with high-performance batch processing and sequential similarity search.

**Sliding Window Strategy:**
- **Window Size**: 512 tokens (accommodates transformer limits)
- **Step Size**: 450 tokens (maintains semantic coherence)
- **Overlap**: 62 tokens (12% overlap prevents information loss)
- **Context Preservation**: Overlapping chunks maintain semantic continuity

**Embedding Generation:**
- **Model**: `as-bessonov/reranker_searchengines_cos2` (768-dimensional)
- **Batch Processing**: 64 texts per batch for optimal GPU utilization
- **Device Optimization**: Automatic CUDA/MPS/CPU selection
- **Normalization**: L2-normalized vectors for cosine similarity

**Vector Storage Configuration:**
- **Storage**: Dense embeddings stored directly in database tables
- **Similarity**: Sequential cosine similarity computation
- **Retrieval**: Direct database queries for relevant chunks
- **Optimization**: Normalized vectors enable efficient dot product similarity

### Component Interaction Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM ARCHITECTURE                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Multi-Session   │    │   Hybrid        │    │   Search API    │
│ Preprocessor    │───▶│   Indexer       │───▶│   Interface     │
│                 │    │                 │    │                 │
│ • URL Normalize │    │ • BM25 + Vector │    │ • /api/search   │
│ • Deduplication │    │ • Bulk Process  │    │ • /batch_search │
│ • Lang Detect   │    │ • Sequential    │    │ • File Export   │
└─────────┬───────┘    └─────────┬───────┘    └─────────────────┘
          │                      │
          │ Prepares Clean Data  │ Orchestrates Indexing
          │                      │
          ▼                      ▼
┌─────────────────┐    ┌─────────────────────────────────────────┐
│ Integrated      │    │              Core Components             │
│ Database        │    │                                         │
│                 │    │ ┌─────────────┐  ┌─────────────────────┐│
│ • Deduplicated  │    │ │ BM25 Engine │  │ Vector Embedder     ││
│ • English Only  │    │ │             │  │                     ││
│ • Standardized  │    │ │ • spaCy NLP │  │ • Reranker Model    ││
│ • Multi-Source  │    │ │ • 4-Table   │  │ • 768-dim Vectors   ││
│                 │    │ │   Schema    │  │ • Sliding Windows   ││
│                 │    │ │ • Adaptive  │  │ • Sequential Search ││
│                 │    │ │   Batching  │  │ • GPU Acceleration  ││
│                 │    │ └─────────────┘  └─────────────────────┘│
│                 │    └─────────────────────────────────────────┘
└─────────────────┘
```

## Usage

### Complete Pipeline

#### 1. Preprocessing Phase (`preprocessor.ipynb`) 

**When to use preprocessing:**
- Multiple crawler databases need integration
- Dataset contains non-English content
- Cross-source URL deduplication required
- Data standardization needed

Run the preprocessing notebook:
```bash
jupyter notebook preprocessor.ipynb
```

**Processing Results:**
- **URL Deduplication**: Aggressive normalization eliminates cross-source duplicates
- **Language Filtering**: Dual-library detection with 15% confidence threshold
- **Data Integration**: Seamless merging with existing databases
- **Quality Assurance**: Standardized formats and referential integrity

#### 2. Hybrid Indexing Phase (`index_all.py`)

Build both BM25 sparse retrieval index and generate dense embeddings:
```bash
python index_all.py
```

**Processing Pipeline:**
1. **BM25 Index Building**: Creates sparse retrieval index with advanced NLP processing
2. **Document Fetching**: 256-document batches from database
3. **Sliding Window Generation**: 512-token windows with 62-token overlap
4. **Embedding Generation**: 64-text batches with GPU acceleration
5. **Bulk Storage**: Optimized database insertion with transaction management
6. **Vector Storage**: Embeddings stored directly in database for sequential search

**BM25 Processing Features:**
- **Adaptive Processing**: Scales from 5,000-document batches to parallel workers
- **Incremental Updates**: Only processes new documents
- **Advanced NLP**: spaCy lemmatization and linguistic filtering
- **Persistent Storage**: Normalized database schema for efficient updates

**Vector Processing Features:**
- **Dense Embeddings**: Using `as-bessonov/reranker_searchengines_cos2` model
- **Sliding Window Chunking**: 512-token windows with 62-token overlap
- **GPU Acceleration**: Optimized batch processing for embedding generation
- **Sequential Search**: Direct database storage for flexible retrieval

> **Note**: The `bm25_indexer.py` script can be run independently for BM25-only indexing, but `index_all.py` handles both BM25 and vector indexing in a single optimized pipeline.



## Database Schema

### Vector Embeddings Schema
```sql
-- Optimized text chunks with metadata
CREATE TABLE chunks_optimized(
    chunk_id BIGINT PRIMARY KEY,
    doc_id BIGINT,
    chunk_text TEXT,
);

-- High-dimensional embeddings for sequential similarity search
CREATE TABLE embeddings(
    chunk_id BIGINT PRIMARY KEY,
    embedding FLOAT[768]  -- Reranker model dimension
);

-- Performance indexes for efficient retrieval
CREATE INDEX idx_chunks_doc_id ON chunks_optimized(doc_id);
```

### BM25 Schema
```sql
-- Complete normalized BM25 schema for efficient sparse retrieval
-- (See BM25 section above for full schema details)
```


## Scalability Features
- **Incremental Processing**: Resume from interruption points
- **Configurable Batching**: Adapt to system memory constraints  
- **Parallel Processing**: Automatic CPU core utilization
- **Sequential Search**: No index overhead during bulk operations

## Dependencies

### Core Libraries
- `duckdb`: OLAP database with vector storage
- `sentence-transformers`: Embedding model infrastructure
- `torch`: Deep learning framework with GPU support
- `spacy`: Advanced NLP processing (`en_core_web_sm`)

### Processing Libraries
- `pandas`: Data manipulation with `swifter` parallel processing
- `numpy`: Numerical operations and array handling
- `tqdm`: Progress tracking and monitoring

### Language Detection
- `langdetect`: Primary language detection
- `polyglot`: Secondary detection with confidence scores

### Optional Extensions
- `cuda`: GPU acceleration (if available)

## Technical Notes

### Model Selection Rationale
- **Reranker Model**: Optimized for search relevance over general embeddings
- **Sliding Windows**: Preserve document structure while enabling transformer processing

### Storage Optimizations
- **Normalized Schema**: Separate concerns for efficient updates and queries
- **Bulk Operations**: Minimize transaction overhead
- **Strategic Indexing**: Performance indexes only where beneficial
- **Sequential Search**: Direct embedding storage for flexible retrieval patterns

### System Integration
- **Multi-Database Support**: Handle distributed crawling architectures
- **Incremental Processing**: Support continuous data ingestion
- **Quality Control**: Comprehensive preprocessing with data validation
- **Hybrid Architecture**: Combine sparse and dense retrieval methods
