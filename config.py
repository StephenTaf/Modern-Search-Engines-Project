EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Default embedding model
EMBEDDING_DIMENSION = 384  # Dimension of the embeddings
MIN_SENTENCE_LENGTH = 5  # Minimum length of sentences to consider
DB_PATH = "index/crawlerDB.duckdb"  # Path to the DuckDB database
DB_TABLE = "urlsDB"  # Table name in the DuckDB database
DEFAULT_BATCH_SIZE = 32  # Default batch size for processing documents
DEFAULT_EMBEDDING_BATCH_SIZE = 64  # Default batch size for embeddings
MAX_CANDIDATES = 1000  # Maximum candidates for hybrid search
DEFAULT_WINDOW_SIZE = 256  # Default window size for sliding windows
DEFAULT_STEP_SIZE = 64  # Default step size for sliding windows

USE_BM25 = False  # Whether to use BM25 for indexing