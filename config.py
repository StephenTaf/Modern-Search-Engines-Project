EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Default embedding model
MIN_SENTENCE_LENGTH = 5  # Minimum length of sentences to consider
DB_PATH = "index/store.duckdb"  # Path to the DuckDB database
DEFAULT_BATCH_SIZE = 64  # Default batch size for processing documents
DEFAULT_EMBEDDING_BATCH_SIZE = 64  # Default batch size for embeddings
MAX_CANDIDATES = 1000  # Maximum candidates for hybrid search