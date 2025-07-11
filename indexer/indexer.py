
from indexer.embedder import TextEmbedder
import config as cfg
import logging
import duckdb
from tqdm import tqdm
from typing import List
import numpy as np
import time
import pandas as pd
import pyarrow as pa
class Indexer:
    def __init__(self,embedder: TextEmbedder,  db_path: str = cfg.DB_PATH):
        """
        Initialize the indexer with database path and embedding model.
        """
        self.embedder = embedder
        self.vdb = duckdb.connect(db_path)
    

    def index_documents(self, batch_size: int = cfg.DEFAULT_BATCH_SIZE, embedding_batch_size: int = cfg.DEFAULT_EMBEDDING_BATCH_SIZE, force_reindex: bool = False):
        """
        Main function to index documents.
        This function will be called by the indexer script.
        """
        _tik = time.time()
        if force_reindex:
            logging.info("Force reindexing enabled. Dropping existing chunks and embeddings.")
            self.vdb.execute("DELETE FROM chunks_optimized")
            self.vdb.execute("DELETE FROM embeddings")
            self.vdb.execute("DROP INDEX IF EXISTS ip_idx;")
            docs_to_index = self.vdb.execute(f"""SELECT id, title, text
                                                FROM urlsDB;""").fetchall()
            
        else:
            docs_to_index = self.vdb.execute(f"""SELECT DISTINCT docs.id, docs.title, docs.text
                                                FROM urlsDB docs
                                                LEFT JOIN chunks_optimized chunks 
                                                    ON docs.id = chunks.doc_id
                                                WHERE chunks.doc_id IS NULL;""").fetchall()
        if len(docs_to_index) == 0:
            logging.info("All documents are already indexed. Skipping indexing.")
            return
        logging.info("Starting document indexing...")
       
        # Get document count
        doc_count = len(docs_to_index)
        logging.info(f"Found {doc_count} documents to index")
        chunk_id = 0
        
        # Process documents in batches
        offset = 0
        with tqdm(total=doc_count, desc="Processing documents") as pbar:
            while offset < doc_count:
                _tik = time.time()
                docs = docs_to_index[offset:offset + batch_size]
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
                
                offset += batch_size
                pbar.update(len(docs))
        
        logging.info(f"Processed {chunk_id} chunks from {doc_count} documents")

        _tik = time.time()
        self.embedder.create_index()  # Create vector index for embeddings
        logging.info(f'vector index created in {time.time() - _tik:.2f} seconds')
        
        logging.info("Indexing completed!")

    
    def _process_embeddings_batch(self, texts: List[str], start_id: int, batch_size: int):
        embedding_data = []

        for i in range(0, len(texts), batch_size):
            _tik = time.time()
            batch = texts[i:i + batch_size]
            embeddings = self.embedder.embedding_model.encode(batch, show_progress_bar=False, normalize_embeddings=True, device=self.embedder.device)

            for j, embedding in enumerate(embeddings):
                chunk_id = start_id + i + j
                embedding_data.append((chunk_id, embedding.astype(np.float32)))
            
            logging.debug(f"Processed {len(batch)} embeddings in {time.time() - _tik:.2f} seconds")

        # Convert to Arrow-backed DataFrame
        if embedding_data:
            _tik = time.time()

            chunk_ids, embedding_arrays = zip(*embedding_data)
            df = pd.DataFrame({
                "chunk_id": chunk_ids,
                "embedding": pa.array(embedding_arrays, type=pa.list_(pa.float32()))
            })

            self.vdb.execute("INSERT INTO embeddings SELECT * FROM df")
            logging.debug(f"Stored {len(embedding_data)} embeddings in {time.time() - _tik:.2f} seconds")
        
    
                
