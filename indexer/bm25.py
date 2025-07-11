import numpy as np
import math
from collections import defaultdict, Counter
from tqdm import tqdm
import logging
import config as cfg
import duckdb
from typing import List
class BM25:
    """Memory-efficient BM25 that stores data in database"""
    def __init__(self, db_connection, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.vdb = db_connection
        self.corpus_size = 0
        self.avgdl = 0
        self._setup_bm25_tables()
        self._load_stats_from_db()
        try:
            import spacy
            self.nlp = spacy.load('en_core_web_sm')
        except OSError:
            logging.warning("spaCy model 'en_core_web_sm' not found. Downloading...")
            import spacy.cli
            spacy.cli.download('en_core_web_sm')
            self.nlp = spacy.load('en_core_web_sm')
            logging.info("spaCy model 'en_core_web_sm' downloaded successfully.")
        
    def _load_stats_from_db(self):
        """Load corpus statistics from database if available"""
        cursor = self.vdb.execute("SELECT key, value FROM bm25_meta WHERE key IN ('corpus_size', 'avgdl');")
        rows = dict(cursor.fetchall())
        self.corpus_size = int(rows.get("corpus_size", 0))
        self.avgdl = float(rows.get("avgdl", 0.0))
        logging.info(f"Loaded BM25 stats: corpus_size={self.corpus_size}, avgdl={self.avgdl}")

    def _save_stats_to_db(self):
        """Save current corpus statistics to database (DuckDB-compatible)"""
        self.vdb.execute("""
            INSERT INTO bm25_meta (key, value) VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value;
        """, ("corpus_size", self.corpus_size))
        
        self.vdb.execute("""
            INSERT INTO bm25_meta (key, value) VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value;
        """, ("avgdl", self.avgdl))
        
    def _setup_bm25_tables(self):
        """Create tables for BM25 data"""
        self.vdb.execute("""
            CREATE TABLE IF NOT EXISTS bm25_terms(
                term TEXT PRIMARY KEY,
                doc_freq INTEGER,
                idf_score REAL
            );
        """)
        
        self.vdb.execute("""
            CREATE TABLE IF NOT EXISTS bm25_sentence_terms(
                sentence_id BIGINT,
                term TEXT,
                term_freq INTEGER,
                PRIMARY KEY (sentence_id, term)
            );
        """)
        
        self.vdb.execute("""
            CREATE TABLE IF NOT EXISTS bm25_sentence_stats(
                sentence_id BIGINT PRIMARY KEY,
                doc_length INTEGER
            );
        """)
        self.vdb.execute("""
            CREATE TABLE IF NOT EXISTS bm25_meta(
                key TEXT PRIMARY KEY,
                value REAL
            );
        """)
        
        # Create indexes for faster lookups
        self.vdb.execute("CREATE INDEX IF NOT EXISTS idx_bm25_sentence_terms_term ON bm25_sentence_terms(term);")
    
    def get_all_tokenized_docs(self, batch_size=cfg.DEFAULT_BATCH_SIZE):
        """Retrieve all tokenized sentences from the database"""
        doc_count = self.vdb.execute(f"SELECT COUNT(*) FROM {cfg.DB_TABLE}").fetchone()[0]
        logging.info(f"Found {doc_count} documents to index")
        
        offset = 0
        all_tokenized_docs = []
        with tqdm(total=doc_count, desc="Processing documents for BM25") as pbar:
            while offset < doc_count:
                docs = self.vdb.execute(
                    f"SELECT id, title, text FROM {cfg.DB_TABLE} LIMIT ? OFFSET ?", 
                    [batch_size, offset]
                ).fetchall()
                if not docs:
                    break
                batch_tokenized = []
                for doc_id, title, text in docs:
                    full_text = f"{title or ''} {text or ''}".strip()
                    if not full_text:
                        continue
                    
                    # Tokenize the text (this should be replaced with actual tokenization logic)
                    tokens = self._tokenize_text(full_text)
                    batch_tokenized.append(tokens)
        all_tokenized_docs.extend(batch_tokenized)
    
    def fit(self):
        """Fit BM25 and store data in database"""
        if self.corpus_size > 0:
            logging.info("BM25 already fitted. Skipping.")
            return
        logging.info("Fitting BM25...")
        # Get all tokenized sentences from the database
        tokenized_docs = self.get_all_tokenized_docs()
        logging.info("Clearing existing BM25 data...")
        self.vdb.execute("DELETE FROM bm25_terms")
        self.vdb.execute("DELETE FROM bm25_sentence_terms") 
        self.vdb.execute("DELETE FROM bm25_sentence_stats")
        
        self.corpus_size = len(tokenized_docs)
        doc_lengths = [len(doc) for doc in tokenized_docs]
        self.avgdl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0
        self._save_stats_to_db()
        logging.info("Computing term frequencies...")
        doc_freqs = {}
        sentence_data = []
        sentence_term_data = []
        
        for sent_id, tokens in enumerate(tqdm(tokenized_docs, desc="Processing docs")):
            sentence_data.append((sent_id, len(tokens)))
            
            # Count term frequencies in this sentence
            term_counts = Counter(tokens)
            for term, freq in term_counts.items():
                sentence_term_data.append((sent_id, term, freq))
                doc_freqs[term] = doc_freqs.get(term, 0) + 1
        
        # Store sentence stats
        self.vdb.executemany(
            "INSERT INTO bm25_sentence_stats (sentence_id, doc_length) VALUES (?, ?)",
            sentence_data
        )
        
        # Store sentence-term data in batches
        batch_size = 10000
        for i in range(0, len(sentence_term_data), batch_size):
            batch = sentence_term_data[i:i + batch_size]
            self.vdb.executemany(
                "INSERT INTO bm25_sentence_terms (sentence_id, term, term_freq) VALUES (?, ?, ?)",
                batch
            )
        
        # Calculate and store IDF values
        logging.info("Computing IDF scores...")
        term_data = []
        for term, freq in tqdm(doc_freqs.items(), desc="Computing IDF"):
            idf_score = math.log(self.corpus_size - freq + 0.5) - math.log(freq + 0.5)
            term_data.append((term, freq, idf_score))
        
        self.vdb.executemany(
            "INSERT INTO bm25_terms (term, doc_freq, idf_score) VALUES (?, ?, ?)",
            term_data
        )
        
        logging.info(f"BM25 fitted on {self.corpus_size} sentences with {len(doc_freqs)} unique terms")
    
    def get_scores(self, query_tokens, limit=1000):
        """Get BM25 scores for query, returning top results only"""
        logging.debug(f"Getting BM25 scores for query: {query_tokens}")
        if not query_tokens:
            return np.array([])
        
        # Get IDF scores for query terms
        placeholders = ','.join(['?' for _ in query_tokens])
        term_idfs = self.vdb.execute(f"""
            SELECT term, idf_score FROM bm25_terms 
            WHERE term IN ({placeholders})
        """, query_tokens).fetchall()
        
        term_idf_dict = dict(term_idfs)
        logging.debug(f"Retrieved IDFscores: {term_idf_dict}")
        if not term_idf_dict:
            return np.array([])
        
        # Get sentences that contain any query terms
        sentence_scores = defaultdict(float)
        
        for term in query_tokens:
            if term in term_idf_dict:
                idf_score = term_idf_dict[term]
                
                # Get sentences containing this term
                results = self.vdb.execute("""
                    SELECT st.sentence_id, st.term_freq, ss.doc_length
                    FROM bm25_sentence_terms st
                    JOIN bm25_sentence_stats ss ON st.sentence_id = ss.sentence_id
                    WHERE st.term = ?
                """, [term]).fetchall()
                logging.debug(f"Found {len(results)} sentences for term '{term}'")
                for sent_id, term_freq, doc_length in results:
                    # Calculate BM25 score for this term in this sentence
                    score = idf_score * term_freq * (self.k1 + 1) / (
                        term_freq + self.k1 * (1 - self.b + self.b * doc_length / self.avgdl)
                    )
                    sentence_scores[sent_id] += score
        
        # Convert to sparse array format
        if not sentence_scores:
            return np.array([])
        
        # Get top scoring sentences only
        top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        logging.debug(f"BM25 Top sentences: {top_sentences[:5]}")
        return top_sentences
    
    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text using spaCy or fallback to basic tokenization"""
        
        doc = self.nlp(text)
        tokens = [token.lemma_.lower() for token in doc 
                    if not token.is_stop and not token.is_punct and token.is_alpha]