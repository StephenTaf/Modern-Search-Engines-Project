from indexer.embedder import TextEmbedder
import config as cfg
import logging
import duckdb
from tqdm import tqdm
from typing import List
import numpy as np
import time
import pandas as pd
class Indexer:
    def __init__(self,embedder: TextEmbedder,  db_path: str = cfg.DB_PATH, read_only: bool = True):
        """
        Initialize the indexer with database path and embedding model.
        """
        self.embedder = embedder
        self.vdb = duckdb.connect(db_path, read_only=read_only)
        
        # Optimize database for bulk operations
        if not read_only:
            self.vdb.execute("PRAGMA threads=4")  # Use multiple threads
            self.vdb.execute("PRAGMA temp_directory='/tmp'")  # Use faster temp directory
            logging.info("Database optimized for bulk operations")

    def index_documents(self, batch_size: int = cfg.DEFAULT_DB_FETCH_BATCH_SIZE, embedding_batch_size: int = cfg.DEFAULT_EMBEDDING_BATCH_SIZE, force_reindex: bool = False):
        """
        Main function to index documents.
        This function fetches documents from the database that are not already indexed, 
        processes them in batches, generates embeddings, and stores them in the optimized database structure.
        
        
        Args:
            batch_size: Number of documents to fetch for processing from the database
            embedding_batch_size: Number of embeddings to generate in each sub-batch
            force_reindex: Whether to reindex all documents
    
        """
        _tik = time.time()
        
            
        if force_reindex:
            logging.info("Force reindexing enabled. Dropping existing chunks and embeddings.")
            self.vdb.execute("DELETE FROM chunks_optimized")
            self.vdb.execute("DELETE FROM embeddings")
            self.vdb.execute("DROP INDEX IF EXISTS ip_idx;")
            self.vdb.execute("DROP INDEX IF EXISTS idx_chunks_opt_doc_id;")
            self.vdb.execute("VACUUM")  # Compact the database
            # Get all document IDs for reindexing
            doc_ids = [row[0] for row in self.vdb.execute("SELECT id FROM urlsDB ORDER BY id").fetchall()]
        else:
            # Get all unindexed document IDs upfront to avoid offset issues
            doc_ids = [row[0] for row in self.vdb.execute("""
                SELECT DISTINCT docs.id
                FROM urlsDB docs
                LEFT JOIN chunks_optimized chunks 
                    ON docs.id = chunks.doc_id
                WHERE chunks.doc_id IS NULL
                ORDER BY docs.id
            """).fetchall()]
        
        doc_count = len(doc_ids)
        
        if doc_count == 0:
            logging.info("All documents are already indexed. Skipping indexing.")
            return
            
        logging.info("Starting document indexing...")
        # Drop existing index to recreate it later. Adding documents to an existing index makes it very slow.
        self.vdb.execute("DROP INDEX IF EXISTS ip_idx;") 
        logging.info(f"Found {doc_count} documents to index")
        
        chunk_id = self._get_next_chunk_id()
        initial_chunk_id = chunk_id
        
        # Process documents in batches using the collected document IDs
        processed_docs = 0
        
        # Using a transaction for bulk inserts. makes it much faster.
        self.vdb.execute("BEGIN TRANSACTION")
        try:
            with tqdm(total=doc_count, desc="Processing documents") as pbar:
                while processed_docs < doc_count:
                    _tik_batch = time.time()
                    
                    # Get batch of document IDs to process
                    batch_doc_ids = doc_ids[processed_docs:processed_docs + batch_size]
                    if not batch_doc_ids:
                        break
                    
                    # Fetch document data for this batch of IDs
                    id_placeholders = ",".join("?" for _ in batch_doc_ids)
                    docs = self.vdb.execute(
                        f"SELECT id, title, text FROM urlsDB WHERE id IN ({id_placeholders}) ORDER BY id",
                        batch_doc_ids
                    ).fetchall()
                    
                    if not docs:
                        break
                    
                    batch_chunks = []
                    batch_texts = []
                    
                    for doc_id, title, text in docs:
                        full_text = f"{title or ''} {text or ''}".strip()
                        if not full_text:
                            continue
                        
                        windows = self.embedder.create_sliding_windows(full_text, window_size=cfg.DEFAULT_WINDOW_SIZE, step_size=cfg.DEFAULT_STEP_SIZE)
                        window_texts = self.embedder.prepare_window_texts(windows)
                        for _, window_text in enumerate(window_texts):
                            batch_chunks.append((chunk_id, doc_id, window_text))
                            batch_texts.append(window_text)
                            chunk_id += 1
                    
                    # Insert chunk metadata
                    if batch_chunks:
                        self.vdb.executemany(
                            "INSERT INTO chunks_optimized (chunk_id, doc_id, chunk_text) VALUES (?, ?, ?)",
                            batch_chunks
                        )

                    # Generate and store embeddings in smaller batches
                    if batch_texts:
                        self._process_embeddings_batch(batch_texts, chunk_id - len(batch_texts), embedding_batch_size)
                    
                    processed_docs += len(docs)
                    pbar.update(len(docs))

                    # Commit every 10 batches documents
                    if processed_docs % (10*batch_size) == 0:
                        self.vdb.execute("COMMIT")
                        self.vdb.execute("BEGIN TRANSACTION")
                        logging.info(f"Committed transaction at {processed_docs} documents")
                    
                    logging.debug(f"Processed batch of {len(docs)} documents in {time.time() - _tik_batch:.2f} seconds")
            
            # Final commit
            self.vdb.execute("COMMIT")
         
        except Exception as e:
            self.vdb.execute("ROLLBACK")
            logging.error(f"Failed during indexing: {e}")
            raise
        
        logging.info(f"Processed {chunk_id - initial_chunk_id} new chunks from {doc_count} documents")

        _tik = time.time()
        self.embedder.create_index()  # Create vector index for embeddings
        logging.info(f'Vector index created in {time.time() - _tik:.2f} seconds')
                
        logging.info("Indexing completed!")
    
    def _get_next_chunk_id(self) -> int:
        """Get the next available chunk ID"""
        result = self.vdb.execute("SELECT COALESCE(MAX(chunk_id), -1) + 1 FROM chunks_optimized").fetchone()
        return result[0] if result else 0

    
    def _process_embeddings_batch(self, texts: List[str], start_id: int, batch_size: int):
        """
        Process embeddings in batches and insert them into the database within a transaction.
        """
        # Collect ALL embeddings first before any database insertions
        all_embedding_data = []
        
        for i in range(0, len(texts), batch_size):
            _tik = time.time()
            batch = texts[i:i + batch_size]
            embeddings = self.embedder.embedding_model.encode(batch, show_progress_bar=False, normalize_embeddings=True, device=self.embedder.device)

            for j, embedding in enumerate(embeddings):
                chunk_id = start_id + i + j
                all_embedding_data.append((chunk_id, embedding.tolist()))
            
            logging.debug(f"Generated {len(batch)} embeddings in {time.time() - _tik:.2f} seconds")

        if all_embedding_data:
            _tik = time.time()
            
            # Create DataFrame and insert in one operation (within existing transaction)
            df = pd.DataFrame(all_embedding_data, columns=["chunk_id", "embedding"])
            self.vdb.execute("INSERT INTO embeddings SELECT * FROM df")
            
            logging.debug(f"Bulk inserted {len(all_embedding_data)} embeddings in {time.time() - _tik:.2f} seconds")
    

    



