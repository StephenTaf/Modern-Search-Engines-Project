import pickle
from typing import List, Dict
from collections import defaultdict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import duckdb
from indexer.bm25 import BM25
from indexer.embedder import TextEmbedder
from indexer.indexer import Indexer
import config as cfg
import logging
class Retriever:
    """
    Retriever class for hybrid search using BM25 and embeddings.
    """
    
    def __init__(self, bm25: BM25, embedder: TextEmbedder, indexer: Indexer, db_path: str = cfg.DB_PATH):
        """
        Initialize the retriever with a DuckDB connection, BM25 instance, and optional embedding model.
        """
        self.vdb = duckdb.connect(db_path)
        self.bm25 = bm25
        self.embedder = embedder
        self.indexer = indexer

    def search(self, query: str, top_k: int = 10, alpha: float = 0.5, max_candidates: int = cfg.MAX_CANDIDATES) -> List[Dict]:
            """
            Memory-efficient hybrid search
            """
            # Tokenize query for BM25
            
            query_tokens = self.indexer._tokenize_text(query)
            logging.debug(f"Query tokens: {query_tokens}")
            # Get BM25 scores (returns list of (sentence_id, score) tuples)
            bm25_results = self.bm25.get_scores(query_tokens, limit=max_candidates)
            
            if not bm25_results:
                return []
            
            # Extract sentence IDs for embedding lookup
            candidate_sentence_ids = [result[0] for result in bm25_results]
            bm25_scores_dict = dict(bm25_results)
            
            # Get embedding similarities for candidates only
            embedding_scores_dict = {}
            if self.embedder.embedding_model:
                query_embedding = self.embedder.embedding_model.encode([query])[0]
                logging.debug(f"Query embedding: {query_embedding[:10]}... (truncated)")
                # Fetch embeddings for candidate sentences only
                placeholders = ','.join(['?' for _ in candidate_sentence_ids])
                embeddings_data = self.vdb.execute(f"""
                    SELECT sentence_id, embedding FROM sentence_embeddings 
                    WHERE sentence_id IN ({placeholders})
                """, candidate_sentence_ids).fetchall()
                
                for sent_id, embedding_blob in embeddings_data:
                    if embedding_blob:
                        embedding = pickle.loads(embedding_blob)
                        similarity = float(cosine_similarity([query_embedding], [embedding])[0][0])
                        embedding_scores_dict[sent_id] = similarity
            
            # Combine scores for candidates
            final_scores = []
            max_bm25 = max(bm25_scores_dict.values()) if bm25_scores_dict else 1.0
            max_embedding = max(embedding_scores_dict.values()) if embedding_scores_dict else 1.0
            
            for sent_id in candidate_sentence_ids:
                bm25_score = bm25_scores_dict.get(sent_id, 0.0) / max_bm25
                embedding_score = embedding_scores_dict.get(sent_id, 0.0) / max_embedding
                hybrid_score = alpha * bm25_score + (1 - alpha) * embedding_score
                
                final_scores.append((sent_id, hybrid_score, bm25_score, embedding_score))
            
            # Sort by hybrid score
            final_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Aggregate by document
            doc_scores = defaultdict(list)
            for sent_id, hybrid_score, bm25_score, embedding_score in final_scores:
                # Get sentence and document info
                sent_info = self.vdb.execute("""
                    SELECT so.doc_id, so.sentence_text, d.url, d.title
                    FROM sentences_optimized so
                    JOIN docs d ON so.doc_id = d.doc_id
                    WHERE so.sentence_id = ?
                """, [sent_id]).fetchone()
                
                if sent_info:
                    doc_id, sentence_text, url, title = sent_info
                    doc_scores[doc_id].append({
                        'sentence_id': sent_id,
                        'sentence': sentence_text,
                        'hybrid_score': hybrid_score,
                        'bm25_score': bm25_score,
                        'embedding_score': embedding_score,
                        'url': url,
                        'title': title
                    })
            
            # Rank documents
            doc_results = []
            for doc_id, sentence_scores in doc_scores.items():
                sentence_scores.sort(key=lambda x: x['hybrid_score'], reverse=True)
                
                doc_results.append({
                    'doc_id': doc_id,
                    'url': sentence_scores[0]['url'],
                    'title': sentence_scores[0]['title'],
                    'max_score': sentence_scores[0]['hybrid_score'],
                    'avg_score': np.mean([s['hybrid_score'] for s in sentence_scores]),
                    'matching_sentences': len(sentence_scores),
                    'best_sentences': sentence_scores[:3]
                })
            
            doc_results.sort(key=lambda x: x['max_score'], reverse=True)
            return doc_results[:top_k]
    def get_document_text(self, doc_id: int):
        """Retrieve full document text"""
        result = self.vdb.execute(
            "SELECT title, text FROM docs WHERE doc_id = ?", [doc_id]
        ).fetchone()
        
        if result:
            title, text = result
            return f"{title or ''}\n\n{text or ''}".strip()
        return None
    