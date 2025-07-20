import duckdb
import math
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import json
import logging
import config as cfg
from tqdm import tqdm
import multiprocessing as mp
from functools import partial

# Global variable to store spaCy model per worker process
_worker_nlp = None

def _process_single_document(doc_data: Tuple[int, str, str], nlp_model_name: str = 'en_core_web_sm') -> Tuple[int, int, Dict[str, int]]:
    """Process a single document - designed to be used in multiprocessing."""
    global _worker_nlp
    
    # Load spaCy model only once per worker process
    if _worker_nlp is None:
        import spacy
        try:
            _worker_nlp = spacy.load(nlp_model_name)
        except OSError:
            _worker_nlp = False 
    
    doc_id, title, text = doc_data
    
    # Combine title and text for processing
    combined_text = f"{title or ''} {text or ''}"
    combined_text = combined_text.lower().replace("tuebingen", "tübingen").replace("tubingen", "tübingen")
    combined_text = combined_text[:1_000_000]  # Limit to 1 million characters, spacy limit
    
    # Tokenize using spaCy or fallback
    if _worker_nlp:
        doc = _worker_nlp(combined_text)
        tokens = [token.lemma_.lower() for token in doc 
                 if not token.is_stop and not token.is_punct and token.is_alpha]
    else:
        print(f"spaCy model not loaded, {doc_id} ignored.")
        tokens = []
    
    if not tokens:
        return doc_id, 0, {}
    
    doc_length = len(tokens)
    term_counts = {}
    
    # Count term frequencies
    for token in tokens:
        term_counts[token] = term_counts.get(token, 0) + 1
    
    return doc_id, doc_length, term_counts

class BM25:
    def __init__(self, db_path: str, k1: float = 1.2, b: float = 0.75, read_only: bool = True):
        """
        Initialize BM25 with DuckDB backend for large-scale processing.
        
        Args:
            db_path: Path to DuckDB database file
            k1: BM25 parameter controlling term frequency scaling
            b: BM25 parameter controlling document length normalization
        """
        self.db_path = db_path
        self.k1 = k1
        self.b = b
        self.conn = duckdb.connect(db_path, read_only=read_only)
        if not read_only:
            self._setup_tables()
        try:
            import spacy
            self.nlp = spacy.load('en_core_web_sm')
        except OSError:
            logging.warning("spaCy model 'en_core_web_sm' not found. Downloading...")
            import spacy.cli
            spacy.cli.download('en_core_web_sm')
            self.nlp = spacy.load('en_core_web_sm')
            logging.info("spaCy model 'en_core_web_sm' downloaded successfully.")
    
    def _setup_tables(self):
        """Create necessary tables for BM25 computation if they don't exist."""
        
        # Table to store document statistics
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bm25_doc_stats (
                doc_id INTEGER PRIMARY KEY,
                doc_length INTEGER,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table to store term frequencies per document
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bm25_term_freq (
                doc_id INTEGER,
                term TEXT,
                freq INTEGER,
                PRIMARY KEY (doc_id, term)
            )
        """)
        
        # Table to store global term statistics
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bm25_term_stats (
                term TEXT PRIMARY KEY,
                doc_freq INTEGER,
                total_freq INTEGER,
                idf_score REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table to store corpus-wide statistics
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bm25_corpus_stats (
                stat_name TEXT PRIMARY KEY,
                stat_value REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_term_freq_term ON bm25_term_freq(term)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_term_freq_doc ON bm25_term_freq(doc_id)")
        
        self.conn.commit()
    
    def _recalculate_idf_scores(self):
        """Recalculate IDF scores for all terms after corpus changes."""
        corpus_stats = self._get_corpus_stats()
        total_docs = corpus_stats.get("total_docs", 1)
        
        print("Recalculating IDF scores...")
        
        # Update IDF scores for all terms in bulk
        idf_update_query = f"""
            UPDATE bm25_term_stats 
            SET idf_score = LOG(({total_docs} - doc_freq + 0.5) / (doc_freq + 0.5)),
                last_updated = CURRENT_TIMESTAMP
        """
        
        self.conn.execute(idf_update_query)
        self.conn.commit()
        
        print("IDF scores updated.")
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text using spaCy"""
        
        doc = self.nlp(text)
        tokens = [token.lemma_.lower() for token in doc 
                    if not token.is_stop and not token.is_punct and token.is_alpha]
        return tokens
    
    def _get_unprocessed_docs_batch(self, offset: int, batch_size: int) -> List[Tuple[int, str, str]]:
        """Get a batch of documents that haven't been processed yet."""
        query = """
            SELECT u.id, u.title, u.text 
            FROM urlsDB u 
            LEFT JOIN bm25_doc_stats s ON u.id = s.doc_id 
            WHERE s.doc_id IS NULL
            ORDER BY u.id
            LIMIT ? OFFSET ?
        """
        return self.conn.execute(query, (batch_size, offset)).fetchall()
    
    def _count_unprocessed_docs(self) -> int:
        """Count total number of unprocessed documents."""
        query = """
            SELECT COUNT(*) 
            FROM urlsDB u 
            LEFT JOIN bm25_doc_stats s ON u.id = s.doc_id 
            WHERE s.doc_id IS NULL
        """
        return self.conn.execute(query).fetchone()[0]
    
    

    def _process_document_batch_parallel(self, documents: List[Tuple[int, str, str]], num_processes: Optional[int] = None) -> Tuple[List[Tuple[int, int]], List[Tuple[int, str, int]], Dict[str, Dict[str, int]]]:
        """Process a batch of documents in parallel and return aggregated term statistics."""
        if not documents:
            return [], [], {}
        
        if num_processes is None:
            num_processes = min(mp.cpu_count()-1, len(documents))
        
        # multiprocessing to process documents in parallel
        with mp.Pool(processes=num_processes) as pool:
            results = pool.map(_process_single_document, documents)
        
        # Aggregate results
        doc_stats = []
        term_freq_data = []
        term_updates = defaultdict(lambda: {'new_docs': 0, 'freq_increase': 0})
        
        for doc_id, doc_length, term_counts in results:
            if doc_length == 0:  # Skip empty documents
                continue
            
            # Collect document statistics
            doc_stats.append((doc_id, doc_length))
            
            # Collect term frequencies for this document
            for term, freq in term_counts.items():
                term_freq_data.append((doc_id, term, freq))
                term_updates[term]['new_docs'] += 1
                term_updates[term]['freq_increase'] += freq
        
        return doc_stats, term_freq_data, term_updates

    def _process_document_batch(self, documents: List[Tuple[int, str, str]]) -> Tuple[List[Tuple[int, int]], List[Tuple[int, str, int]], Dict[str, Dict[str, int]]]:
        """Process a batch of documents and return aggregated term statistics."""
        # Use parallel processing for larger batches
        if len(documents) >= 50:  
            return self._process_document_batch_parallel(documents)
        
        # Original sequential processing for smaller batches
        doc_stats = []
        term_freq_data = []
        term_updates = defaultdict(lambda: {'new_docs': 0, 'freq_increase': 0})
        
        for doc_id, title, text in documents:
            
            combined_text = f"{title or ''} {text or ''}"
            combined_text = combined_text[:1_000_000]  # Limit to 1 million characters, spacy limit
            combined_text = combined_text.lower().replace("tuebingen", "tübingen").replace("tubingen", "tübingen")
            tokens = self._tokenize(combined_text)
            
            if not tokens:
                continue
            
            doc_length = len(tokens)
            term_counts = defaultdict(int)
            
            # Count term frequencies
            for token in tokens:
                term_counts[token] += 1
            
            # Collect document statistics
            doc_stats.append((doc_id, doc_length))
            
            # Collect term frequencies for this document
            for term, freq in term_counts.items():
                term_freq_data.append((doc_id, term, freq))
                term_updates[term]['new_docs'] += 1
                term_updates[term]['freq_increase'] += freq
        
        return doc_stats, term_freq_data, term_updates
    
    def build_index(self, batch_size: int = cfg.DEFAULT_DB_FETCH_BATCH_SIZE_FOR_BM25):
        """Build or update BM25 index incrementally."""
        print("Building/updating BM25 index...")
        
        total_docs = self._count_unprocessed_docs()
        
        if total_docs == 0:
            print("No new documents to process.")
            self._update_corpus_stats()
            return
        
        print(f"Processing {total_docs} new documents...")
        
        processed = 0
        offset = 0
        
        with tqdm(total=total_docs, desc="Processing documents") as pbar:
            while processed < total_docs:
                # Get batch of unprocessed documents
                batch = self._get_unprocessed_docs_batch(offset, batch_size)
                
                if not batch:
                    break
                
                # Start transaction for this batch
                self.conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Process the batch and get aggregated data
                    doc_stats, term_freq_data, term_updates = self._process_document_batch(batch)
                    
                    # Bulk insert document statistics
                    if doc_stats:
                        self.conn.executemany(
                            "INSERT OR REPLACE INTO bm25_doc_stats (doc_id, doc_length) VALUES (?, ?)",
                            doc_stats
                        )
                    
                    # Bulk insert term frequencies
                    if term_freq_data:
                        self.conn.executemany(
                            "INSERT OR REPLACE INTO bm25_term_freq (doc_id, term, freq) VALUES (?, ?, ?)",
                            term_freq_data
                        )
                    
                    # Update term statistics
                    if term_updates:
                        # First, get existing term stats for terms in this batch
                        terms_to_check = list(term_updates.keys())
                        placeholders = ','.join(['?' for _ in terms_to_check])
                        existing_stats = self.conn.execute(
                            f"SELECT term, doc_freq, total_freq FROM bm25_term_stats WHERE term IN ({placeholders})",
                            terms_to_check
                        ).fetchall()
                        
                        existing_dict = {term: (doc_freq, total_freq) for term, doc_freq, total_freq in existing_stats}
                        
                        # Prepare bulk update data
                        term_stats_updates = []
                        for term, updates in term_updates.items():
                            if term in existing_dict:
                                old_doc_freq, old_total_freq = existing_dict[term]
                                new_doc_freq = old_doc_freq + updates['new_docs']
                                new_total_freq = old_total_freq + updates['freq_increase']
                            else:
                                new_doc_freq = updates['new_docs']
                                new_total_freq = updates['freq_increase']
                            
                            term_stats_updates.append((term, new_doc_freq, new_total_freq))
                        
                        # Bulk update term statistics
                        self.conn.executemany(
                            "INSERT OR REPLACE INTO bm25_term_stats (term, doc_freq, total_freq) VALUES (?, ?, ?)",
                            term_stats_updates
                        )
                    
                    # Commit transaction
                    self.conn.commit()
                    
                    processed += len(batch)
                    pbar.update(len(batch))
                    print(f"Processed {processed}/{total_docs} documents")
                    
                except Exception as e:
                    # Rollback on error
                    self.conn.execute("ROLLBACK")
                    print(f"Error processing batch: {e}")
                    raise
            
        # Update corpus-wide statistics and recalculate IDF scores
        self._update_corpus_stats()
        self._recalculate_idf_scores()
        print("Index building complete!")
    
    def _update_corpus_stats(self):
        """Update corpus-wide statistics like average document length."""
        # Calculate average document length
        avg_doc_length = self.conn.execute(
            "SELECT AVG(doc_length) FROM bm25_doc_stats"
        ).fetchone()[0]
        
        # Get total number of documents
        total_docs = self.conn.execute(
            "SELECT COUNT(*) FROM bm25_doc_stats"
        ).fetchone()[0]
        
        # Store corpus statistics
        self.conn.execute(
            "INSERT OR REPLACE INTO bm25_corpus_stats (stat_name, stat_value) VALUES (?, ?)",
            ("avg_doc_length", avg_doc_length or 0)
        )
        
        self.conn.execute(
            "INSERT OR REPLACE INTO bm25_corpus_stats (stat_name, stat_value) VALUES (?, ?)",
            ("total_docs", total_docs)
        )
        
        self.conn.commit()
    
    def _get_corpus_stats(self) -> Dict[str, float]:
        """Get corpus-wide statistics."""
        stats = {}
        results = self.conn.execute(
            "SELECT stat_name, stat_value FROM bm25_corpus_stats"
        ).fetchall()
        
        for stat_name, stat_value in results:
            stats[stat_name] = stat_value
        
        return stats
    
    def search(self, query: str, top_k: int = 1000, min_score: float = 0.0) -> List[Tuple[int, float, str, str]]:
        """
        Search documents using BM25 scoring.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            min_score: Minimum BM25 score threshold
            
        Returns:
            List of tuples (doc_id, score, title, text_snippet)
        """
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        
        # Get corpus statistics
        corpus_stats = self._get_corpus_stats()
        avg_doc_length = corpus_stats.get("avg_doc_length", 1.0)
        total_docs = corpus_stats.get("total_docs", 1)
        
        # Get unique query terms and their frequencies in the query
        query_term_freq = defaultdict(int)
        for term in query_terms:
            query_term_freq[term] += 1
        
        unique_terms = list(query_term_freq.keys())
        
        # Get term statistics for query terms (including pre-calculated IDF)
        placeholders = ','.join(['?' for _ in unique_terms])
        term_stats_query = f"""
            SELECT term, doc_freq, total_freq, idf_score 
            FROM bm25_term_stats 
            WHERE term IN ({placeholders})
        """
        term_stats_results = self.conn.execute(term_stats_query, unique_terms).fetchall()
        
        # Create term stats dictionary
        term_stats = {}
        for term, doc_freq, total_freq, idf_score in term_stats_results:
            term_stats[term] = {
                'doc_freq': doc_freq,
                'total_freq': total_freq,
                'idf': idf_score or 0.0  # Handle NULL case
            }
        
        # Skip terms that don't exist in the corpus
        valid_terms = [term for term in unique_terms if term in term_stats]
        if not valid_terms:
            return []
        
        # Get documents that contain at least one query term
        valid_placeholders = ','.join(['?' for _ in valid_terms])
        candidate_docs_query = f"""
            SELECT DISTINCT
                tf.doc_id,
                tf.term,
                tf.freq,
                ds.doc_length
            FROM bm25_term_freq tf
            JOIN bm25_doc_stats ds ON tf.doc_id = ds.doc_id
            WHERE tf.term IN ({valid_placeholders})
            ORDER BY tf.doc_id
        """
        
        candidate_results = self.conn.execute(candidate_docs_query, valid_terms).fetchall()
        
        # Group results by document
        doc_terms = defaultdict(dict)
        doc_lengths = {}
        
        for doc_id, term, freq, doc_length in candidate_results:
            doc_terms[doc_id][term] = freq
            doc_lengths[doc_id] = doc_length
        
        # Calculate BM25 scores
        doc_scores = []
        
        for doc_id, term_freqs in doc_terms.items():
            doc_length = doc_lengths[doc_id]
            bm25_score = 0.0
            
            # Calculate score for each query term in this document
            for term in valid_terms:
                if term in term_freqs:
                    tf = term_freqs[term]  # term frequency in document
                    idf = term_stats[term]['idf']  # inverse document frequency
                    
                    # BM25 formula components
                    tf_component = (tf * (self.k1 + 1)) / (
                        tf + self.k1 * (1 - self.b + self.b * doc_length / avg_doc_length)
                    )
                    
                    # Add to total score (multiply by query term frequency)
                    term_score = idf * tf_component * query_term_freq[term]
                    bm25_score += term_score
            
            if bm25_score >= min_score:
                doc_scores.append((doc_id, bm25_score))
        
        # Sort by score descending and limit results
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        top_docs = doc_scores[:top_k]
        
        if not top_docs:
            return []
        
        # Get document details for top results
        doc_ids = [doc_id for doc_id, _ in top_docs]
        doc_placeholders = ','.join(['?' for _ in doc_ids])
        
        docs_query = f"""
            SELECT id, title, text
            FROM urlsDB
            WHERE id IN ({doc_placeholders})
        """
        
        doc_details = self.conn.execute(docs_query, doc_ids).fetchall()
        doc_details_dict = {doc_id: (title, text) for doc_id, title, text in doc_details}
        
        # Build final results with document details
        final_results = []
        for doc_id, score in top_docs:
            if doc_id in doc_details_dict:
                title, text = doc_details_dict[doc_id]
                text_snippet = (text or '')[:200]
                if len(text or '') > 200:
                    text_snippet += '...'
                
                final_results.append({"doc_id": doc_id, "score": score, "text_snippet": text_snippet})
        
        return final_results
    
    def get_term_stats(self, term: str) -> Optional[Dict]:
        """Get statistics for a specific term."""
        result = self.conn.execute(
            "SELECT doc_freq, total_freq FROM bm25_term_stats WHERE term = ?",
            (term.lower(),)
        ).fetchone()
        
        if result:
            doc_freq, total_freq = result
            corpus_stats = self._get_corpus_stats()
            total_docs = corpus_stats.get("total_docs", 1)
            
            return {
                "term": term,
                "document_frequency": doc_freq,
                "total_frequency": total_freq,
                "inverse_document_frequency": math.log((total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
            }
        
        return None
    
    def get_document_terms(self, doc_id: int, limit: int = 20) -> List[Tuple[str, int]]:
        """Get top terms for a specific document."""
        results = self.conn.execute(
            "SELECT term, freq FROM bm25_term_freq WHERE doc_id = ? ORDER BY freq DESC LIMIT ?",
            (doc_id, limit)
        ).fetchall()
        
        return results
    
    def get_index_stats(self) -> Dict:
        """Get overall index statistics."""
        corpus_stats = self._get_corpus_stats()
        
        unique_terms = self.conn.execute(
            "SELECT COUNT(*) FROM bm25_term_stats"
        ).fetchone()[0]
        
        processed_docs = self.conn.execute(
            "SELECT COUNT(*) FROM bm25_doc_stats"
        ).fetchone()[0]
        
        total_docs_in_db = self.conn.execute(
            "SELECT COUNT(*) FROM urlsDB"
        ).fetchone()[0]
        
        return {
            "total_documents_in_database": total_docs_in_db,
            "processed_documents": processed_docs,
            "unique_terms": unique_terms,
            "average_document_length": corpus_stats.get("avg_doc_length", 0),
            "index_coverage": f"{processed_docs}/{total_docs_in_db} ({100 * processed_docs / max(total_docs_in_db, 1):.1f}%)"
        }
    

