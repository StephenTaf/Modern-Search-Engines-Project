# Indexer Module

The indexer module is responsible for processing and indexing documents from the crawled data to enable efficient search and retrieval. It provides semantic search capabilities using text embeddings and optional BM25 scoring.

## Overview

This module processes documents from a DuckDB database, generates embeddings for text chunks, and stores them in an optimized database structure for fast retrieval. The indexer supports both semantic search through embeddings and traditional keyword-based search through BM25.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INDEXING PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Raw Crawled    │    │  Preprocessing  │    │   Text Chunking │    │   Embedding     │    │  Vector Index   │
│  Data (Multi-   │───▶│  (Language +    │───▶│   (Sliding      │───▶│   Generation    │───▶│   (HNSW)        │
│  Source)        │    │  Deduplication) │    │   Window)       │    │   (SentenceT)   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │                       │
         │                       │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ • Multiple DBs  │    │ • URL Normalize │    │ • Window Size:  │    │ • Model:        │    │ • Algorithm:    │
│ • Document ID   │    │ • Duplicate     │    │   256 tokens    │    │   all-MiniLM-   │    │   HNSW          │
│ • Title         │    │   Removal       │    │ • Step Size:    │    │   L6-v2         │    │ • Metric:       │
│ • Full Text     │    │ • Language      │    │   200 tokens    │    │ • Dimension:    │    │   Inner Product │
│ • URL           │    │   Detection     │    │ • Overlap for   │    │   384           │    │ • Index Name:   │
│ • Mixed Lang    │    │ • English Only  │    │   context       │    │ • Normalized    │    │   ip_idx        │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE LAYER                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Raw Data (Multi)│    │ chunks_optimized│    │   embeddings    │    │   VSS Extension │
│                 │    │                 │    │                 │    │                 │
│ • crawler_v4.db │    │ • chunk_id      │    │ • chunk_id      │    │ • HNSW Index    │
│ • crawlerDb.db  │───▶│ • doc_id        │───▶│ • embedding     │───▶│ • Fast ANN      │
│ • Others        │    │ • chunk_text    │    │   [384 dims]    │    │   Search        │
│                 │    │                 │    │                 │    │ • Persistence   │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PROCESSING FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

1. Load Multiple Data Sources
   ↓
2. Preprocessing (Language Detection + Deduplication)
   ↓
3. Fetch Documents (Batch: 100)
   ↓
4. Text Chunking (Sliding Window)
   ↓
5. Embedding Generation (Batch: 64)
   ↓
6. Store in Database (Optimized Tables)
   ↓
7. Create HNSW Index (Vector Search)
   ↓
8. Ready for ANN Search
```

## Configuration

The indexer uses configuration parameters from `config.py`:

- **EMBEDDING_MODEL**: `"all-MiniLM-L6-v2"` - The sentence transformer model used for embeddings
- **EMBEDDING_DIMENSION**: `384` - Dimension of the embedding vectors
- **MIN_SENTENCE_LENGTH**: `5` - Minimum length of sentences to consider for indexing
- **DB_PATH**: `"crawlerDB.duckdb"` - Path to the DuckDB database
- **DB_TABLE**: `"urlsDB"` - Table name containing the crawled documents
- **DEFAULT_BATCH_SIZE**: `32` - Default batch size for processing documents
- **DEFAULT_EMBEDDING_BATCH_SIZE**: `64` - Batch size for generating embeddings
- **DEFAULT_DB_FETCH_BATCH_SIZE**: `100` - Batch size for fetching documents from database
- **DEFAULT_WINDOW_SIZE**: `256` - Window size for text chunking
- **DEFAULT_STEP_SIZE**: `200` - Step size for sliding window chunking
- **USE_BM25**: `False` - Whether to use BM25 for indexing (currently disabled)

## Components

### Preprocessing Pipeline (`preprocessor.ipynb`)

Before the indexing process begins, the data goes through a comprehensive preprocessing pipeline to ensure data quality and consistency.

**Key Features:**
- **Data Merging**: Combines crawled data from multiple sources and databases
- **Duplicate Detection**: Removes duplicate URLs using normalized URL comparison
- **Language Detection**: Filters content to include only English text using dual validation
- **Data Standardization**: Normalizes data formats and column structures
- **Database Integration**: Merges new data with existing database while maintaining data integrity

**Processing Steps:**

1. **Data Loading**: Connects to multiple DuckDB databases and loads crawled data
2. **URL Normalization**: 
   - Removes protocol prefixes (http://, https://)
   - Strips query parameters and trailing slashes
   - Enables accurate duplicate detection across sources
3. **Duplicate Removal**:
   - Removes URLs already present in existing database
   - Eliminates duplicates within new data
   - Reduces data redundancy and processing overhead
4. **Language Detection**:
   - Uses dual language detection approach with `langdetect` and `polyglot`
   - Accepts content if either library detects English with ≥15% confidence
   - Filters out non-English content to improve search relevance
5. **Data Standardization**:
   - Assigns sequential IDs to new documents
   - Converts timestamps to Unix format
   - Normalizes column names and structure
6. **Database Integration**:
   - Merges preprocessed data with existing database
   - Recreates database tables with combined data
   - Maintains referential integrity


**Dependencies:**
- `duckdb`: Database operations
- `pandas`: Data manipulation and analysis
- `langdetect`: Primary language detection
- `polyglot`: Secondary language detection with confidence scores
- `swifter`: Parallel processing for pandas operations

### Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COMPONENT ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ preprocessor.   │    │   index_all.py  │    │   Retriever     │
│ ipynb           │───▶│  (Entry Point)  │───▶│   (Search)      │
│ (Preprocessing) │    │                 │    │                 │
│ • langdetect    │    │                 │    │                 │
│ • polyglot      │    │                 │    │                 │
│ • swifter       │    │                 │    │                 │
│ • URL normalize │    │                 │    │                 │
│ • Deduplication │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────────────┘
          │                      │
          │ Prepares Data        │ Orchestrates
          │                      │
          ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ Multiple Raw    │    │   Indexer       │
│ Data Sources    │    │  (indexer.py)   │
│ • crawler_v4.db │    └─────────┬───────┘
│ • crawlerDb.db  │              │
│ • Others        │              │ Uses
└─────────────────┘              │
                                 │
                       ┌─────────▼───────┐
                       │  TextEmbedder   │
                       │  (embedder.py)  │
                       └─────────┬───────┘
                                 │
                                 │ Manages
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ SentenceT       │    │    DuckDB       │    │   VSS Extension │
│ Model           │    │   Database      │    │   (HNSW Index)  │
│                 │    │                 │    │                 │
│ • Encoding      │    │ • Tables        │    │ • Vector Index  │
│ • GPU/CPU       │    │ • Persistence   │    │ • ANN Search    │
│ • Batching      │    │ • Optimization  │    │ • Inner Product │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         

                       ┌─────────────────┐
                       │      BM25       │
                       │   (bm25.py)     │
                       │   [Optional]    │
                       │                 │
                       │ • Keyword       │
                       │   Search        │
                       │ • spaCy NLP     │
                       │ • Database      │
                       │   Storage       │
                       └─────────────────┘
```

### 1. TextEmbedder (`embedder.py`)

The core component responsible for generating and managing text embeddings.

**Key Features:**
- Uses SentenceTransformer models for embedding generation
- Supports GPU acceleration (CUDA/MPS) when available
- Creates optimized database tables for storing embeddings
- Implements HNSW (Hierarchical Navigable Small World) vector index for fast ANN search
- Handles batch processing of text chunks
- Provides similarity search functionality using inner product metric

**Database Tables:**
- `chunks_optimized`: Stores text chunks with document references
- `embeddings`: Stores embedding vectors for each chunk with HNSW index

**Vector Index:**
- Uses DuckDB's VSS extension with HNSW algorithm
- Creates `ip_idx` index on embedding column using inner product metric
- Enables experimental persistence for index durability
- Supports approximate nearest neighbor (ANN) search for fast retrieval

### 2. Indexer (`indexer.py`)

The main indexing engine that processes documents and coordinates the embedding generation.

**Key Features:**
- Processes documents in configurable batches
- Generates text chunks using sliding window approach
- Manages database operations and optimization
- Supports force reindexing of all documents
- Provides progress tracking and logging

**Main Method:**
- `index_documents()`: Main function that processes documents, generates embeddings, and stores them

### 3. BM25 (`bm25.py`)

Traditional keyword-based search implementation (currently disabled by default).

**Key Features:**
- Memory-efficient BM25 implementation
- Stores data in database for persistence
- Uses spaCy for text preprocessing
- Supports configurable parameters (k1, b)
- Provides keyword-based document scoring

## Usage

### Complete Pipeline

The complete indexing pipeline consists of two main phases:

#### 1. Preprocessing Phase (`preprocessor.ipynb`) - *Optional*

**Note**: This step is optional and only required if you need to:
- Merge data from multiple crawler databases
- Remove non-English documents from your dataset
- Deduplicate URLs across different data sources

If you already have a clean, single-source database with English content, you can skip directly to the indexing phase.

Run the preprocessing notebook to prepare and clean the data: 
```bash
jupyter notebook preprocessor.ipynb
```

**What it does:**
- Loads data from multiple crawler databases
- Normalizes URLs and removes duplicates
- Performs dual-language detection to filter English content
- Merges new data with existing database
- Prepares clean, deduplicated dataset for indexing

**Key Preprocessing Steps:**
- **Data Sources**: Connects to multiple DuckDB files
- **URL Normalization**: Removes protocols, query parameters, and trailing slashes
- **Deduplication**: Eliminates duplicates within and across data sources
- **Language Detection**: Uses both langdetect and polyglot libraries
- **Data Merging**: Combines preprocessed data with existing database

#### 2. Indexing Phase (`index_all.py`)

After preprocessing, run the main indexing script:

```bash
python index_all.py
```

**What it does:**
1. Initialize the text embedder with the configured model
2. Set up the indexer instance
3. Process all documents in the database
4. Generate embeddings for text chunks
5. Store results in optimized database tables
6. Create HNSW vector index for fast search


### Key Configuration Options

- **Batch Processing**: Adjust `DEFAULT_DB_FETCH_BATCH_SIZE` and `DEFAULT_EMBEDDING_BATCH_SIZE` based on system's memory and processing capabilities
- **Text Chunking**: Modify `DEFAULT_WINDOW_SIZE` and `DEFAULT_STEP_SIZE` to control how documents are split into chunks
- **Embedding Model**: Change `EMBEDDING_MODEL` to use different sentence transformer models
- **Force Reindexing**: Set `force_reindex=True` in the `index_documents()` call to rebuild the entire index

### Device Support

The embedder automatically detects and uses the best available compute device:
- **CUDA**: For NVIDIA GPUs
- **MPS**: For Apple Silicon Macs
- **CPU**: Fallback for systems without GPU support

## Database Schema

The indexer creates the following optimized database structure:

```sql
-- Text chunks table
CREATE TABLE chunks_optimized(
    chunk_id BIGINT PRIMARY KEY,
    doc_id BIGINT,
    chunk_text TEXT
);

-- Embeddings table  
CREATE TABLE embeddings(
    chunk_id BIGINT PRIMARY KEY,
    embedding FLOAT[384]  -- Dimension matches EMBEDDING_DIMENSION
);

-- HNSW Vector Index for fast ANN search
CREATE INDEX ip_idx ON embeddings USING HNSW (embedding)
    WITH (metric = 'ip');  -- Inner product metric

-- Traditional indexes for performance
CREATE INDEX idx_chunks_opt_doc_id ON chunks_optimized(doc_id);
```

**Vector Search Setup:**
- Installs and loads DuckDB's VSS (Vector Similarity Search) extension
- Enables experimental persistence for HNSW index durability
- Registers embedding function for query-time embedding generation
- Uses inner product metric for similarity calculations

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                           │
└─────────────────────────────────────────────────────────────────────────────────┘

Input: Multiple Data Sources
┌─────────────────┐                           ┌─────────────────┐    
│ newly_crawl.db  │                           │ crawlerDb.db    │    
│ ┌─────────────┐ │                           │ ┌─────────────┐ │   
│ │ Added docs  │ │                           │ │ Existing    │ │   
│ │             │ │                           │ │ Database    │ │   
│ │ Multi-lang  │ │                           │ │             │ │   
│ └─────────────┘ │                           │ └─────────────┘ │  
└─────────┬───────┘                           └─────────┬───────┘    
          │                                             │
          │                                             │
          └─────────────────────────────────────────────┘
                                 │
                                 │ Preprocessing Pipeline
                                 │
                       ┌─────────▼───────┐
                       │ URL Normalize   │
                       │ + Deduplication │
                       └─────────┬───────┘
                                 │
                                 │ Language Detection
                                 │
                       ┌─────────▼───────┐
                       │ English Filter  │
                       │ ┌─────────────┐ │
                       │ │ langdetect  │ │
                       │ │ + polyglot  │ │ 
                       │ └─────────────┘ │
                       └─────────┬───────┘
                                 │
                                 │ Merge with Existing Data
                                 │
┌────────────────────────────────▼───────────────────────────────┐
│                          Clean Database                        │
│                         ┌─────────────┐                        │
│                         │ id: 1       │                        │
│                         │ title: "X"  │                        │
│                         │ text: "..." │                        │
│                         │ url: "..."  │                        │
│                         │ (English)   │                        │
│                         └─────────────┘                        │
└────────────────────────────────────────────────────────────────┘
                                │
                                │ Batch Fetch (100 docs)
                                │
                      ┌─────────▼───────┐
                      │ Text Chunking   │
                      │ ┌─────────────┐ │
                      │ │ Window: 256 │ │
                      │ │ Step: 200   │ │
                      │ │ Overlap: 56 │ │
                      │ └─────────────┘ │
                      └─────────┬───────┘
                                │
                                │ Produces Multiple Chunks
                                │
                      ┌─────────▼───────┐
                      │ Text Chunks     │
                      │ ┌─────────────┐ │
                      │ │ chunk_id: 1 │ │
                      │ │ doc_id: 1   │ │
                      │ │ text: "..." │ │
                      │ └─────────────┘ │
                      └─────────┬───────┘
                                │
                                │ Embedding Generation (Batch: 64)
                                │
                      ┌─────────▼───────┐
                      │ Embeddings      │
                      │ ┌─────────────┐ │
                      │ │ chunk_id: 1 │ │
                      │ │ vector:     │ │
                      │ │ [0.1, 0.2,  │ │
                      │ │  ..., 0.8]  │ │
                      │ │ (384 dims)  │ │
                      │ └─────────────┘ │
                      └─────────┬───────┘
                                │
                                │ Storage & Indexing
                                │
                      ┌─────────▼───────┐
                      │ HNSW Index      │
                      │ ┌─────────────┐ │
                      │ │ Fast ANN    │ │
                      │ │ Search      │ │
                      │ │ Ready       │ │
                      │ └─────────────┘ │
                      └─────────────────┘

Query Time Flow:
Query → Embedding → HNSW Search → Top-K Results
```

## Performance Optimization

The indexer includes several performance optimizations:

- **Batch Processing**: Documents are processed in configurable batches to balance memory usage and performance
- **Database Optimization**: Uses multiple threads and optimized temporary directories
- **GPU Acceleration**: Automatic detection and use of available GPU resources
- **Memory Management**: Efficient handling of large document collections through streaming
- **HNSW Vector Index**: Hierarchical Navigable Small World algorithm for fast approximate nearest neighbor search
- **Traditional Indexing**: Database indexes on frequently queried columns
- **VSS Extension**: Leverages DuckDB's Vector Similarity Search extension for optimized vector operations
- **Normalized Embeddings**: Unit-length embeddings for consistent similarity calculations

## Logging

The indexer provides comprehensive logging information including:
- Device detection and usage
- Processing progress and timing
- Database optimization status
- Batch processing statistics
- Error handling and recovery

## Dependencies

- `sentence-transformers`: For embedding generation
- `duckdb`: Database operations and vector similarity search
- `vss`: DuckDB extension for vector similarity search and HNSW indexing
- `torch`: Deep learning framework
- `spacy`: Text preprocessing (for BM25)
- `numpy`: Numerical operations
- `tqdm`: Progress bars
- `pandas`: Data manipulation

## Notes

- The BM25 functionality is currently disabled by default (`USE_BM25 = False`)
- The indexer supports both incremental and full reindexing
- All database operations are optimized for bulk processing
