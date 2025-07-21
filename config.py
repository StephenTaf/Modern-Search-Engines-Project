EMBEDDING_MODEL = "as-bessonov/reranker_searchengines_cos2"# Default embedding model, self trained
EMBEDDING_DIMENSION = 768  # Dimension of the embeddings
DB_PATH = "crawlerDB.db"   # Path to the DuckDB database
DB_TABLE = "urlsDB"  # Table name in the DuckDB database

DEFAULT_DB_FETCH_BATCH_SIZE_FOR_BM25 = 5000  # Default batch size for fetching documents for BM25

DEFAULT_EMBEDDING_BATCH_SIZE = 64  # Default batch size for embeddings
DEFAULT_DB_FETCH_BATCH_SIZE = 256  # Default batch size for fetching documents from database
DEFAULT_WINDOW_SIZE = 512  # Default window size for sliding windows
DEFAULT_STEP_SIZE = 450  # Default step size for sliding windows

TOP_K_RETRIEVAL = 1000  # Default number of top results to return in retrieval
TOP_K_RERANKING = 100  # Default number of top results to return in reranking

# Reranker API Configuration
RERANKER_API_URL = "http://localhost:8000/rerank"  # URL for the reranker API
RERANKER_TIMEOUT = 200  # Timeout for reranker API requests in seconds

LLM_API_URL = "http://localhost:1984/generate_summary"  # URL for the LLM API
LLM_TIMEOUT = 200  # Timeout for LLM API requests in seconds
LLM_MAX_WINDOWS = 10  # Maximum number of windows to process in LLM API

USE_BM25 = True  # Whether to use BM25 for indexing, 