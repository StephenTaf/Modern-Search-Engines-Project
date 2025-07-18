EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Default embedding model
EMBEDDING_DIMENSION = 384  # Dimension of the embeddings
MIN_SENTENCE_LENGTH = 5  # Minimum length of sentences to consider
DB_PATH = "crawlerDb.duckdb"  # Path to the DuckDB database
DB_TABLE = "urlsDB"  # Table name in the DuckDB database
DEFAULT_BATCH_SIZE = 32  # Default batch size for processing documents
DEFAULT_EMBEDDING_BATCH_SIZE = 64  # Default batch size for embeddings
DEFAULT_DB_FETCH_BATCH_SIZE = 256  # Default batch size for fetching documents from database
MAX_CANDIDATES = 1000  # Maximum candidates for hybrid search
DEFAULT_WINDOW_SIZE = 256  # Default window size for sliding windows
DEFAULT_STEP_SIZE = 200  # Default step size for sliding windows

TOP_K_RETRIEVAL = 200  # Default number of top results to return in retrieval
TOP_K_RERANKING = 100  # Default number of top results to return in reranking

# Reranker API Configuration
RERANKER_API_URL = "http://localhost:8000"  # Base URL for the reranker API# Whether to use the reranker API
RERANKER_TIMEOUT = 100  # Timeout for reranker API requests in seconds

USE_BM25 = False  # Whether to use BM25 for indexing, we do not use it anymore