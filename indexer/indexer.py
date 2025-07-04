from indexer.bm25 import BM25
from indexer.embedder import TextEmbedder
import config as cfg
import logging
import duckdb
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from typing import List, Tuple, Dict
import numpy as np
import pickle
import re

class Indexer:
    def __init__(self, bm25: BM25,embedder: TextEmbedder,  db_path: str = cfg.DB_PATH):
        """
        Initialize the indexer with database path and embedding model.
        """
        self.embedder = embedder
        self.bm25 = bm25
        self.vdb = duckdb.connect(db_path)
        try:
            import spacy
            self.nlp = spacy.load('en_core_web_sm')
        except OSError:
            logging.warning("spaCy model 'en_core_web_sm' not found. Downloading...")
            import spacy.cli
            spacy.cli.download('en_core_web_sm')
            self.nlp = spacy.load('en_core_web_sm')
            logging.info("spaCy model 'en_core_web_sm' downloaded successfully.")
      

    def index_documents(self, batch_size: int = cfg.DEFAULT_BATCH_SIZE, embedding_batch_size: int = cfg.DEFAULT_EMBEDDING_BATCH_SIZE, force_reindex: bool = False):
        """
        Main function to index documents.
        This function will be called by the indexer script.
        """
        if not force_reindex:
            sentence_count = self.vdb.execute("SELECT COUNT(*) FROM sentences_optimized").fetchone()[0]
            if sentence_count > 0:
                logging.info("Index already exists. Skipping indexing.")
                return
        logging.info("Starting document indexing...")
        # Connect to the DuckDB database
        self.vdb.execute("DELETE FROM sentences_optimized")
        self.vdb.execute("DELETE FROM sentence_embeddings")
        
        # Get document count
        doc_count = self.vdb.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        logging.info(f"Found {doc_count} documents to index")
        sentence_id = 0
        all_tokenized_sentences = []
        
        # Process documents in batches
        offset = 0
        with tqdm(total=doc_count, desc="Processing documents") as pbar:
            while offset < doc_count:
                docs = self.vdb.execute(
                    "SELECT doc_id, title, text FROM docs LIMIT ? OFFSET ?", 
                    [batch_size, offset]
                ).fetchall()
                
                if not docs:
                    break
                
                batch_sentences = []
                batch_texts = []
                batch_tokenized = []
                
                for doc_id, title, text in docs:
                    full_text = f"{title or ''} {text or ''}".strip()
                    if not full_text:
                        continue
                    
                    sentences = self._split_into_sentences(full_text, doc_id)
                    
                    for order, (sentence_text, _) in enumerate(sentences):
                        batch_sentences.append((sentence_id, doc_id, sentence_text, order, 0.0))
                        batch_texts.append(sentence_text)
                        
                        # Tokenize for BM25
                        tokens = self._tokenize_text(sentence_text)
                        batch_tokenized.append(tokens)
                        
                        sentence_id += 1
                
                # Insert sentence metadata
                if batch_sentences:
                    self.vdb.executemany(
                        "INSERT INTO sentences_optimized (sentence_id, doc_id, sentence_text, sentence_order, embedding_norm) VALUES (?, ?, ?, ?, ?)",
                        batch_sentences
                    )
                
                # Store tokenized sentences for BM25
                all_tokenized_sentences.extend(batch_tokenized)
                
                # Generate and store embeddings in smaller batches
                if self.embedder.embedding_model and batch_texts:
                    self._process_embeddings_batch(batch_texts, sentence_id - len(batch_texts), embedding_batch_size)
                
                offset += batch_size
                pbar.update(len(docs))
        
        logging.info(f"Processed {sentence_id} sentences from {doc_count} documents")
        
        # Fit BM25 (this will store data in database)
        logging.info("Training BM25...")
        self.bm25.fit(all_tokenized_sentences)
        
        logging.info("Indexing completed!")
        
    def _process_embeddings_batch(self,texts: List[str], start_id: int, batch_size: int):
            """Process embeddings in small batches to manage memory"""
            embedding_data = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                embeddings = self.embedder.embedding_model.encode(batch, show_progress_bar=False)
                
                for j, embedding in enumerate(embeddings):
                    sentence_id = start_id + i + j
                    embedding_blob = pickle.dumps(embedding.astype(np.float32))
                    embedding_norm = float(np.linalg.norm(embedding))
                    
                    embedding_data.append((sentence_id, embedding_blob))
                    
                    # Update norm in sentences table
                    self.vdb.execute(
                        "UPDATE sentences_optimized SET embedding_norm = ? WHERE sentence_id = ?",
                        [embedding_norm, sentence_id]
                    )
            
            # Store embeddings
            if embedding_data:
                self.vdb.executemany(
                    "INSERT INTO sentence_embeddings (sentence_id, embedding) VALUES (?, ?)",
                    embedding_data
                )
                
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text"""
        text = re.sub(r'\s+', ' ', text.strip())
        return text
    
    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text using spaCy or fallback to basic tokenization"""
        
        doc = self.nlp(text)
        tokens = [token.lemma_.lower() for token in doc 
                    if not token.is_stop and not token.is_punct and token.is_alpha]
        return tokens
    def _split_into_sentences(self, text: str, doc_id: int) -> List[Tuple[str, int]]:
        """Split text into sentences"""
        doc = self.nlp(text)
        sentences = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if len(sent_text) > cfg.MIN_SENTENCE_LENGTH:  # Filter short sentences
                sentences.append((self._preprocess_text(sent_text), doc_id))
        return sentences