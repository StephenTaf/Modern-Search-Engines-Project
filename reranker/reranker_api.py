import os
from typing import List, Dict, Tuple, Optional, Union
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import yaml
import logging
import time
import json
from collections import deque

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from transformers import AutoTokenizer
import asyncio
import duckdb
from urllib.parse import urlparse
from sentence_transformers import SentenceTransformer
import pandas as pd

class Database:
    def __init__(self, data_path: str):
        """Initialize database by connecting to duckdb ."""
        self.vdb = duckdb.connect(data_path, read_only=True)
        self.data_path = data_path
    
    def get_documents_by_ids(self, doc_ids: Union[str, List[str]]) -> List[Dict]:
        """Get all documents matching the given doc_id(s)."""
        if isinstance(doc_ids, str):
            doc_ids = [doc_ids]
        
        placeholders = ', '.join(['?'] * len(doc_ids))
        # Use GROUP BY url to get distinct URLs, normalizing URLs by removing query parameters
        # This treats URLs as the same if they only differ by query parameters (e.g., ?q=vf)
        # Take max (first) 10 chunks per document for memory efficiency
        query = f"""
            WITH url_data AS (
                SELECT CAST(MIN(id) AS TEXT) AS id, 
                    FIRST(title) AS title, 
                    FIRST(url) AS url, 
                    FIRST(text) AS text 
                FROM urlsDB 
                WHERE id IN ({placeholders}) 
                GROUP BY CASE 
                    WHEN INSTR(url, '?') > 0 THEN SUBSTR(url, 1, INSTR(url, '?') - 1)
                    ELSE url 
                END
            ),
            ranked_chunks AS (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY doc_id) as rn
                FROM chunks_optimized
            )
            
            SELECT ud.*, co.*, e.*
            FROM url_data ud
            JOIN ranked_chunks co ON ud.id = co.doc_id
            JOIN embeddings e ON co.chunk_id = e.chunk_id
            WHERE co.rn <= 10
            """
        
        results = self.vdb.execute(query, doc_ids).df()
        
        return results #[{'doc_id': row[0], 'title': row[1], 'url': row[2], 'text': row[3]} for row in results]



# Global rate limiter state
class RateLimiter:
    def __init__(self, max_requests_per_minute: int):
        self.max_requests_per_minute = max_requests_per_minute
        self.request_times = deque()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request, waiting if necessary to respect rate limits."""
        async with self.lock:
            current_time = time.time()
            
            # Remove requests older than 1 minute
            while self.request_times and current_time - self.request_times[0] >= 60:
                self.request_times.popleft()
            
            # If we're at the limit, wait until we can make another request
            if len(self.request_times) >= self.max_requests_per_minute:
                sleep_time = 60 - (current_time - self.request_times[0]) + 0.1  # Small buffer
                logger.info(f"Rate limit reached. Waiting {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)
                
                # Clean up old requests again after waiting
                current_time = time.time()
                while self.request_times and current_time - self.request_times[0] >= 60:
                    self.request_times.popleft()
            
            # Record this request
            self.request_times.append(current_time)

# Load configuration
def load_config(config_path: str = "reranker/config.yaml") -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file {config_path} not found. Please ensure config.yaml exists.")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing configuration file: {e}")

# Load configuration
config = load_config()

# Setup logging
logging.basicConfig(
    level=getattr(logging, config['logging']['level']),
    format=config['logging']['format']
)
logger = logging.getLogger(__name__)

# Initialize database
database = Database(config['database']['data_path'])

# Initialize rate limiter
rate_limiter = None
if config.get('rate_limiting', {}).get('enabled', False):
    max_rpm = config['rate_limiting']['requests_per_minute']
    rate_limiter = RateLimiter(max_rpm)
    logger.info(f"Rate limiting enabled: {max_rpm} requests per minute")

# Initialize FastAPI app with config
app = FastAPI(
    title=config['server']['title'],
    version=config['server']['version'],
    description=config['server']['description']
)

# Initialize tokenizer from config
HF_MODEL_NAME = config['huggingface']['model_name']
logger.info(f"Loading model: {HF_MODEL_NAME}")
embedding_model = SentenceTransformer(HF_MODEL_NAME)

class RerankRequest(BaseModel):
    doc_ids: List[str]  # List of document IDs to rerank
    similarities: Optional[List[float]] = None  # Optional list of similarity scores for each document
    query: str
    # window_size: int = config['sliding_window']['default_window_size']
    # step_size: int = config['sliding_window']['default_step_size']
    # top_n: int = config['sliding_window']['default_top_n']

class WindowScore(BaseModel):
    text: str
    similarity_score: float
    doc_id: str
    title: str
    window_index: int

class DocumentScore(BaseModel):
    doc_id: str
    title: str
    url: str
    similarity_score: float
    original_similarity: float  # Original retrieval similarity score
    most_relevant_window:WindowScore

class RerankResponse(BaseModel):
    document_scores: List[DocumentScore]
    top_windows: List[WindowScore]
    total_documents: int
    total_windows: int

def extract_domain(url):
    """Extract domain from URL - basic version"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return "defaultdomain"

def apply_domain_cap(results, max_per_domain=2):
    """
        Filter out same domains. Input must be sorted by similatity score!
    """
    domain_counts = {}
    filtered_results = []
    dropped_results = []
    
    for doc in results:
        domain = extract_domain(doc.url)
        if domain_counts.get(domain, 0) < max_per_domain:
            filtered_results.append(doc)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        else:
            dropped_results.append(doc)
    
    return filtered_results, dropped_results

def hybrid_diversification(results, relevance_threshold=0.8, top_k=100):
    """
    use max 1 per domain due to the fact that we don't want to be same domains in medium relevance group
    """
    
    # Separate high-relevance from medium-relevance
    high_relevance_domains = set([extract_domain(doc.url) for doc in results if doc.similarity_score >= relevance_threshold])
    medium_relevance_domains = set([extract_domain(doc.url) for doc in results if doc.similarity_score < relevance_threshold])
    medium_relevance_domains = medium_relevance_domains.difference(high_relevance_domains) # exclude high priority domains from medium priority
    high_rel = [doc for doc in results if (doc.similarity_score >= relevance_threshold or extract_domain(doc.url) in high_relevance_domains)] # will NOT be sorted
    # "and" because some medium results were qualified as high due to domain
    medium_rel = [doc for doc in results if (doc.similarity_score < relevance_threshold and extract_domain(doc.url) in medium_relevance_domains)] # will NOT be sorted
    
    high_rel = sorted(high_rel, key=lambda x: x.similarity_score, reverse=True)
    medium_rel = sorted(medium_rel, key=lambda x: x.similarity_score, reverse=True)
    # Apply strict diversity to high-relevance results
    diversified_high, dropped_high = apply_domain_cap(high_rel, max_per_domain=1) # will be sorted
    
    # Fill remaining slots with medium-relevance, allowing more per domain
    remaining_slots = top_k - len(diversified_high) # Other slots will be filled with this
    diversified_medium, dropped_medium = apply_domain_cap(medium_rel, max_per_domain=1) # will be sorted
    
    # Combine and maintain relevance order within diversity constraints
    final_results = sorted(diversified_high + diversified_medium[:remaining_slots], key=lambda x: x.similarity_score, reverse=True)
    rest_docs = sorted(dropped_high + dropped_medium, key=lambda x: x.similarity_score, reverse=True)
    if len(final_results) < top_k:
        # Note: Here would be better to use recursion hybrid_diversification(rest_docs, top_k=need_to_add), but there are corner cases when it's not convergent
        # Note: I fill rest with mixed results because it looks to be native
        need_to_add = top_k - len(final_results)
        additional = rest_docs[:need_to_add]
        if additional:
            # need to update scores in tail to be monotonical
            # additional is already sorted
            eps=1e-4
            last_relevant_score = final_results[-1].similarity_score
            delta = additional[0].similarity_score - last_relevant_score + eps # > 0
            for doc in additional:
                doc.similarity_score = max(0.0, doc.similarity_score - delta)
            final_results.extend(additional)
    
    return sorted(final_results, key=lambda x: x.similarity_score, reverse=True)


def create_sliding_windows(tokens: List[int], window_size: int, step_size: int) -> List[List[int]]:
    if len(tokens) <= window_size:
        return [tokens]
    
    windows = []
    # Generate all possible windows using step_size
    for i in range(0, len(tokens) - window_size + 1, step_size):
        window = tokens[i:i + window_size]
        windows.append(window)
    
    # Calculate start index for the last full-size window
    last_window_start = len(tokens) - window_size
    
    # Add last full window if:
    # 1. It starts at a valid position (non-negative)
    # 2. It wasn't already generated by the loop
    #    (i.e., its start index isn't a multiple of step_size)
    if last_window_start >= 0 and last_window_start % step_size != 0:
        last_window = tokens[last_window_start:last_window_start + window_size]
        windows.append(last_window)
    
    return windows

def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """Calculate similarity between two embeddings based on config metric."""
    # Convert to numpy arrays for similarity calculation
    emb1_array = np.array(embedding1).reshape(1, -1)
    emb2_array = np.array(embedding2).reshape(1, -1)
    
    # metric == "cosine":
    similarity = cosine_similarity(emb1_array, emb2_array)[0][0]
    return float(similarity)


def get_new_similarity(documents, query_embedding, batch_size: int) -> List[float]:
    """
    Calculate new similarity scores for documents based on query embedding.
    Uses batch processing to handle large datasets efficiently.
    """
    similarities = []
    
    # Process in batches
    for i in range(0, len(documents), batch_size):
        batch_docs = documents.iloc[i:i + batch_size]
        doc_embeddings = np.array([doc[1]['embedding'] for doc in batch_docs.iterrows()])  # Extract embeddings from DataFrame
        # Calculate cosine similarity for the entire batch
        batch_similarities = cosine_similarity(query_embedding.reshape(1, -1), doc_embeddings)[0]
        similarities.extend(batch_similarities)
    return similarities

def normalise_similarities(similarities: List[float]) -> List[float]:
    """Normalise similarity scores to a range of [0, 1]."""
    min_sim = min(similarities)
    max_sim = max(similarities)
    if max_sim == min_sim:
        # If all similarities are identical, avoid division by zero
        return [0.0 for _ in similarities]
    return [(sim - min_sim) / (max_sim - min_sim) for sim in similarities]


def apply_positional_weighting(group):
    """Apply positional weighting to the best chunk in each group.
    Boosts the first chunk and decays the last chunk based on their positions.
    idea: To boost a document if its first chunk (assumingly, with title) is the best one."""
    # Sort chunks by chunk_id to get positional order
    sorted_chunks = group.sort_values('chunk_id')
    total_chunks = len(sorted_chunks)
    if total_chunks == 1:
        return group
    # Find position of best chunk (0-indexed)
    best_chunk_id = group.loc[group['new_similarity'].idxmax(), 'chunk_id']
    position = sorted_chunks[sorted_chunks['chunk_id'] == best_chunk_id].index[0]
    chunk_position = sorted_chunks.index.get_loc(position)
    
    # Calculate position ratio (0 = first chunk, 1 = last chunk)
    position_ratio = chunk_position / max(1, total_chunks - 1) if total_chunks > 1 else 0
    
    # boost/decay parameters
    max_boost = 0.1  # 10% boost for first chunk
    max_decay = 0.05  # 5% decay for last chunk
    
    # Linear interpolation: first chunk gets boost, last chunk gets decay
    position_adjustment = max_boost - (max_boost + max_decay) * position_ratio
    
    # Apply adjustment to the best chunk's similarity
    best_idx = group['new_similarity'].idxmax()
    original_sim = group.loc[best_idx, 'new_similarity']
    adjusted_sim = original_sim + position_adjustment
    
    # Ensure similarity stays within valid bounds [0, 1]
    adjusted_sim = max(0.0, min(1.0, adjusted_sim))
    
    # Update the similarity score
    group.loc[best_idx, 'new_similarity'] = adjusted_sim
    
    return group

@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """
    Rerank documents based on similarity to query using sliding window approach.
    """
    try:
        #logger.info(f"Processing rerank request for doc_ids: {request.doc_ids} with similarities: {request.similarities}")
        logger.info(f"Query: {request.query[:100]}{'...' if len(request.query) > 100 else ''}") 
        TOP_K= config['similarity'].get('top_k', 100)  # Default to 100 if not specified in config
        # Get documents from database
        documents = database.get_documents_by_ids(request.doc_ids) 

        if len(documents) == 0:
            raise HTTPException(status_code=401, detail="No documents found for the provided doc_ids")

        logger.info(f"Found {len(documents)} documents in database")
        
        query_text = request.query

        query_embedding = embedding_model.encode(query_text) 
        # get old similarity as provided
        documents = documents.merge(pd.DataFrame({"doc_id":[int(d_id) for d_id in request.doc_ids], "old_similarity" : request.similarities}), on=['doc_id'])
        documents["new_similarity"] = get_new_similarity(documents, query_embedding, config['similarity']['batch_size'])
        # make smoothing
        documents['new_similarity'] = normalise_similarities(documents['new_similarity'].tolist())
        documents['old_similarity'] = normalise_similarities(documents['old_similarity'].tolist())
        documents['new_similarity'] = documents['new_similarity'] *(1-config["similarity"]["smoothing"]) + documents['old_similarity'] * config["similarity"]["smoothing"]
        documents = documents.reset_index(drop=True)

        
        # Apply positional weighting to each document group
        documents = documents.groupby('doc_id').apply(apply_positional_weighting).reset_index(drop=True)

        # Calculate idx after positional adjustments
        idx = documents.groupby('doc_id')['new_similarity'].idxmax()
        reranked_documents = documents.loc[idx, ['id', 'title', 'url', 'text', 'chunk_id', 'doc_id', 'chunk_text', 'new_similarity', 'old_similarity']]
        reranked_documents = reranked_documents.sort_values(by="new_similarity", ascending=False).reset_index(drop=True)
        # below list is sorted!
        document_scores = []
        
        for i, doc in reranked_documents.iterrows():
            try:
                document_scores.append(
                    DocumentScore(
                        doc_id=str(doc['doc_id']),
                        title=doc['title'],
                        url=doc['url'],
                    similarity_score=doc['new_similarity'],
                    original_similarity=doc['old_similarity'],
                    most_relevant_window=WindowScore(
                        text=doc['text'],
                        similarity_score=doc['new_similarity'],
                        doc_id=str(doc['doc_id']),
                        title=doc['title'],
                        window_index=doc['chunk_id']  

                    )
                )
                )
            except Exception as e:
                logger.error(f"Error creating DocumentScore objects: {e}")
                continue
        
        if config['similarity'].get('diversification', False):
            logger.debug("Applying domain diversification to results")
            reranked_docs = hybrid_diversification(document_scores, top_k=TOP_K)
        else:
            logger.debug("Skipping hybrid diversification, returning top results as is")
            reranked_docs = document_scores[:TOP_K]
       # reranked_docs = document_scores[:TOP_K]#hybrid_diversification(document_scores, top_k=TOP_K)  # Apply hybrid diversification to the top 100 documents
        logger.info(f"Reranking completed. Top document: {document_scores[0].doc_id} ({document_scores[0].similarity_score:.4f})")
        return RerankResponse(
            document_scores=reranked_docs,
            top_windows=[doc.most_relevant_window for doc in reranked_docs[:TOP_K]],
            total_documents=len(documents),
            total_windows=TOP_K
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint with configuration information."""
    return {
        "status": "healthy",
        "model": HF_MODEL_NAME,
        "embedding_model": config['openai']['embedding_model'],
        "default_window_size": config['sliding_window']['default_window_size'],
        "default_step_size": config['sliding_window']['default_step_size'],
        "supported_extensions": config['file_processing']['supported_extensions'],
        "version": config['server']['version'],
        "rate_limiting_enabled": config.get('rate_limiting', {}).get('enabled', False),
        "database": {
            "data_path": config['database']['data_path'],
            "total_documents": database.get_document_count(),
            "unique_doc_ids": database.get_unique_doc_count()
        }
    }

@app.get("/database/info")
async def get_database_info():
    """Get information about the loaded database."""
    return {
        "data_path": database.data_path,
        "total_documents": database.get_document_count(),
        "unique_doc_ids": database.get_unique_doc_count(),
        "sample_doc_ids": database.get_all_doc_ids()[:10]  # Show first 10 doc_ids as sample
    }

@app.get("/database/doc-ids")
async def get_all_doc_ids():
    """Get list of all available doc_ids in the database."""
    return {
        "doc_ids": database.get_all_doc_ids(),
        "total_count": database.get_unique_doc_count()
    }

@app.get("/database/documents/{doc_id}")
async def get_documents_by_id(doc_id: str):
    """Get all documents with the specified doc_id."""
    documents = database.get_documents_by_ids(doc_id)
    if not documents:
        raise HTTPException(status_code=404, detail=f"No documents found for doc_id: {doc_id}")
    
    return {
        "doc_id": doc_id,
        "documents": documents,
        "count": len(documents)
    }

@app.post("/database/reload")
async def reload_database():
    """Reload the database from the JSON file."""
    try:
        database.load_data()
        return {
            "status": "success",
            "message": "Database reloaded successfully",
            "total_documents": database.get_document_count(),
            "unique_doc_ids": database.get_unique_doc_count()
        }
    except Exception as e:
        logger.error(f"Error reloading database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reloading database: {str(e)}")

@app.get("/rate-limit-status")
async def get_rate_limit_status():
    """Get current rate limiting status and usage statistics."""
    if not config.get('rate_limiting', {}).get('enabled', False) or not rate_limiter:
        return {
            "rate_limiting_enabled": False,
            "message": "Rate limiting is disabled"
        }
    
    async with rate_limiter.lock:
        current_time = time.time()
        
        # Clean up old requests
        while rate_limiter.request_times and current_time - rate_limiter.request_times[0] >= 60:
            rate_limiter.request_times.popleft()
        
        requests_in_last_minute = len(rate_limiter.request_times)
        max_requests = rate_limiter.max_requests_per_minute
        remaining_requests = max(0, max_requests - requests_in_last_minute)
        
        # Calculate time until oldest request expires (when we can make more requests)
        time_until_reset = 0
        if rate_limiter.request_times:
            time_until_reset = max(0, 60 - (current_time - rate_limiter.request_times[0]))
    
    return {
        "rate_limiting_enabled": True,
        "max_requests_per_minute": max_requests,
        "requests_in_last_minute": requests_in_last_minute,
        "remaining_requests": remaining_requests,
        "time_until_reset_seconds": round(time_until_reset, 2),
        "utilization_percentage": round((requests_in_last_minute / max_requests) * 100, 1)
    }

@app.get("/config")
async def get_config():
    """Get current configuration (excluding sensitive information)."""
    safe_config = config.copy()
    # Hide sensitive information
    if 'openai' in safe_config and 'api_key' in safe_config['openai']:
        safe_config['openai']['api_key'] = "***hidden***"
    
    return safe_config

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": config['server']['title'],
        "version": config['server']['version'],
        "description": config['server']['description'],
        "database_info": {
            "total_documents": database.get_document_count(),
            "unique_doc_ids": database.get_unique_doc_count()
        },
        "endpoints": {
            "/rerank": "POST - Rerank documents based on query similarity",
            "/health": "GET - Health check with configuration info",
            "/config": "GET - Current configuration (safe)",
            "/rate-limit-status": "GET - Rate limiting status and usage statistics",
            "/database/info": "GET - Database information and statistics",
            "/database/doc-ids": "GET - List all available doc_ids",
            "/database/documents/{doc_id}": "GET - Get documents by doc_id",
            "/database/reload": "POST - Reload database from file",
            "/docs": "GET - API documentation"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting {config['server']['title']} v{config['server']['version']}")
    logger.info(f"Using model: {HF_MODEL_NAME}")
    logger.info(f"Server will run on {config['server']['host']}:{config['server']['port']}")
    
    uvicorn.run(
        app, 
        host=config['server']['host'], 
        port=config['server']['port']
    )
