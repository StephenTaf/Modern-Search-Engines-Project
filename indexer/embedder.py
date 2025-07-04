import duckdb
from sentence_transformers import SentenceTransformer
import logging
import config as cfg

class TextEmbedder:
    def __init__(self, db_path: str, embedding_model: str = cfg.EMBEDDING_MODEL):
        """
        Memory-optimized hybrid search engine for large document collections
        """
        self.db_path = db_path
        self.vdb = duckdb.connect(db_path)    
        self.embedding_model = SentenceTransformer(embedding_model)
        self._setup_database()
         
    def _setup_database(self):
        """Create optimized table structure"""
        self.vdb.execute("""
            CREATE TABLE IF NOT EXISTS sentences_optimized(
              sentence_id BIGINT PRIMARY KEY,
              doc_id      BIGINT,
              sentence_text TEXT,
              sentence_order INTEGER,
              embedding_norm REAL,  -- Store just the norm for quick filtering
              FOREIGN KEY (doc_id) REFERENCES docs(doc_id)
            );
        """)
        
        # Create indexes
        self.vdb.execute("CREATE INDEX IF NOT EXISTS idx_sentences_opt_doc_id ON sentences_optimized(doc_id);")
        self.vdb.execute("CREATE INDEX IF NOT EXISTS idx_sentences_opt_norm ON sentences_optimized(embedding_norm);")
        
        # Separate table for embeddings 
        self.vdb.execute("""
            CREATE TABLE IF NOT EXISTS sentence_embeddings(
              sentence_id BIGINT PRIMARY KEY,
              embedding BLOB
            );
        """)
    
    