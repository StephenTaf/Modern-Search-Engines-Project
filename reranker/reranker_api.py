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
        query = f"""
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
        """
        
        results = self.vdb.execute(query, doc_ids).fetchall()
        
        return [{'doc_id': row[0], 'title': row[1], 'url': row[2], 'text': row[3]} for row in results]

# Database class for document indexing
# class Database:
#     def __init__(self, data_path: str):
#         """Initialize database by loading JSON file with document records."""
#         self.data_path = data_path
#         self.documents = []
#         self.doc_index = {}  # doc_id -> list of record indices
#         self.load_data()
    
#     def load_data(self):
#         """Load documents from JSON file and build index."""
#         try:
#             with open(self.data_path, 'r', encoding='utf-8') as f:
#                 self.documents = json.load(f)
            
#             if not isinstance(self.documents, list):
#                 raise ValueError("JSON file must contain a list of document records")
            
#             # Build index: doc_id -> list of indices
#             self.doc_index = {}
#             for i, doc in enumerate(self.documents):
#                 if not isinstance(doc, dict):
#                     raise ValueError(f"Document at index {i} must be a dictionary")
                
#                 required_fields = ['doc_id', 'title', 'url', 'text', 'similarity']
#                 missing_fields = [field for field in required_fields if field not in doc]
#                 if missing_fields:
#                     raise ValueError(f"Document at index {i} missing required fields: {missing_fields}")
                
#                 doc_id = str(doc['doc_id'])
#                 if doc_id not in self.doc_index:
#                     self.doc_index[doc_id] = []
#                 self.doc_index[doc_id].append(i)
            
#             logger.info(f"Loaded {len(self.documents)} documents with {len(self.doc_index)} unique doc_ids from {self.data_path}")
            
#         except FileNotFoundError:
#             raise FileNotFoundError(f"Database file not found: {self.data_path}")
#         except json.JSONDecodeError as e:
#             raise ValueError(f"Invalid JSON in database file: {e}")
#         except Exception as e:
#             raise ValueError(f"Error loading database: {e}")
    
    # def get_documents_by_ids(self, doc_ids: Union[str, List[str]]) -> List[Dict]:
    #     """Get all documents matching the given doc_id(s)."""
    #     if isinstance(doc_ids, str):
    #         doc_ids = [doc_ids]
        
    #     result = []
    #     missing_ids = []
        
    #     for doc_id in doc_ids:
    #         if doc_id in self.doc_index:
    #             # Get all documents with this doc_id
    #             for index in self.doc_index[doc_id]:
    #                 result.append(self.documents[index])
    #         else:
    #             missing_ids.append(doc_id)
        
    #     if missing_ids:
    #         logger.warning(f"Documents not found for doc_ids: {missing_ids}")
        
    #     return result
    
    # def get_all_doc_ids(self) -> List[str]:
    #     """Get list of all available doc_ids."""
    #     return list(self.doc_index.keys())
    
    # def get_document_count(self) -> int:
    #     """Get total number of documents."""
    #     return len(self.documents)
    
    # def get_unique_doc_count(self) -> int:
    #     """Get number of unique doc_ids."""
    #     return len(self.doc_index)

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
logger.info(f"Loading tokenizer: {HF_MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_NAME)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Initialize OpenAI client from config
api_key = config['openai']['api_key']
# Initialize OpenAI client with optional base_url for alternative providers
openai_config = {"api_key": api_key}
if 'base_url' in config['openai']:
    openai_config['base_url'] = config['openai']['base_url']
    logger.info(f"Using custom API base URL: {config['openai']['base_url']}")

openai_client = OpenAI(**openai_config)
logger.info("OpenAI client initialized successfully")

class RerankRequest(BaseModel):
    doc_ids: List[str]  # List of document IDs to rerank
    similarities: Optional[List[float]] = None  # Optional list of similarity scores for each document
    query: str
    window_size: int = config['sliding_window']['default_window_size']
    step_size: int = config['sliding_window']['default_step_size']
    top_n: int = config['sliding_window']['default_top_n']
    call_api: Optional[bool] = True  # Whether to call the model for embeddings

class DocumentScore(BaseModel):
    doc_id: str
    title: str
    url: str
    similarity_score: float
    original_similarity: float  # Original retrieval similarity score

class WindowScore(BaseModel):
    text: str
    similarity_score: float
    doc_id: str
    title: str
    window_index: int

class RerankResponse(BaseModel):
    document_scores: List[DocumentScore]
    top_windows: List[WindowScore]
    total_documents: int
    total_windows: int

def tokenize_text(text: str, add_special_tokens: bool = True) -> List[int]:
    """Tokenize text using the HuggingFace tokenizer."""
    tokens = tokenizer.encode(text, add_special_tokens=add_special_tokens)
    return tokens

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

def decode_tokens(tokens: List[int]) -> str:
    """Decode tokens back to text."""
    return tokenizer.decode(tokens, skip_special_tokens=True)

def prepare_window_texts(windows: List[List[int]]) -> List[str]:
    """Convert token windows back to properly formatted text with special tokens."""
    window_texts = []
    for window in windows:
        # Decode window tokens back to text (without special tokens)
        window_text = tokenizer.decode(window, skip_special_tokens=True)
        window_texts.append(window_text)
    return window_texts

def get_embedding(text: str) -> List[float]:
    """Get embedding from API for a single text."""
    try:
        response = openai_client.embeddings.create(
            model=config['openai']['embedding_model'],
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error getting embedding: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting embedding: {str(e)}")

def get_embeddings_batch_api(texts: List[str]) -> List[List[float]]:
    """Get embeddings for multiple texts in a single API call."""
    try:
        response = openai_client.embeddings.create(
            model=config['openai']['embedding_model'],
            input=texts  # Send all texts in one request
        )
        # Extract embeddings in the same order as input texts
        embeddings = []
        for data_item in response.data:
            embeddings.append(data_item.embedding)
        return embeddings
    except Exception as e:
        logger.error(f"Error getting batch embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting batch embeddings: {str(e)}")

async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Get embeddings for multiple texts using batched API calls with RPM control."""
    # Use batch size from config
    batch_size = config['openai']['batch_size']
    
    logger.info(f"Processing {len(texts)} texts in batches of {batch_size}")
    
    # Calculate RPM limits
    use_rpm_control = config.get('rate_limiting', {}).get('enabled', False)
    
    if use_rpm_control:
        max_rpm = config.get('rate_limiting', {}).get('requests_per_minute', 60)
        logger.info(f"RPM control enabled: max {max_rpm} requests per minute")
    
    # Collect async tasks for parallel execution
    tasks = []
    batch_info = []  # Keep track of batch info for logging
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        # Apply rate limiting if enabled (one API call per batch)
        if use_rpm_control and rate_limiter:
            await rate_limiter.acquire()
        
        # Start async task without waiting - this allows parallel execution
        task = asyncio.to_thread(get_embeddings_batch_api, batch)
        tasks.append(task)
        
        batch_num = i//batch_size + 1
        total_batches = (len(texts) + batch_size - 1)//batch_size
        batch_info.append((batch_num, total_batches, len(batch)))
        
        # Add a small delay between batch starts to be extra safe with rate limits
        if use_rpm_control and batch_num < total_batches:
            await asyncio.sleep(0.1)
    
    # Wait for all API calls to complete in parallel
    logger.debug(f"Waiting for {len(tasks)} parallel API calls to complete...")
    # NOTE: asyncio.gather() preserves order - results match input task order regardless of completion order
    all_batch_results = await asyncio.gather(*tasks)
    
    # Flatten results and log completion
    all_embeddings = []
    for i, (batch_embeddings, (batch_num, total_batches, batch_size_actual)) in enumerate(zip(all_batch_results, batch_info)):
        all_embeddings.extend(batch_embeddings)
        logger.debug(f"Completed batch {batch_num}/{total_batches} ({batch_size_actual} texts in 1 API call)")
    
    return all_embeddings

async def process_windows_batched(all_windows: List[Dict]) -> None:
    """
    Process all windows in batches to get embeddings and add them to the window dictionaries.
    
    Args:
        all_windows: List of window dictionaries, each containing 'doc_id', 'text', 'window_id'
                    The 'embedding' key will be added to each dictionary.
    """
    if not all_windows:
        return
    
    # Extract all window texts
    window_texts = [window['text'] for window in all_windows]
    
    logger.info(f"Getting embeddings for {len(window_texts)} windows using batched API calls")
    
    # Get embeddings in batches
    embeddings = await get_embeddings_batch(window_texts)
    
    # Add embeddings back to the window dictionaries
    for window, embedding in zip(all_windows, embeddings):
        window['embedding'] = embedding
    
    logger.debug(f"Successfully added embeddings to {len(all_windows)} windows")

def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """Calculate similarity between two embeddings based on config metric."""
    # Convert to numpy arrays for similarity calculation
    emb1_array = np.array(embedding1).reshape(1, -1)
    emb2_array = np.array(embedding2).reshape(1, -1)
    
    # metric == "cosine":
    similarity = cosine_similarity(emb1_array, emb2_array)[0][0]
    return float(similarity)

@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """
    Rerank documents based on similarity to query using sliding window approach.
    """
    try:
        logger.info(f"Processing rerank request for doc_ids: {request.doc_ids} with similarities: {request.similarities}")
        logger.info(f"Query: {request.query[:100]}{'...' if len(request.query) > 100 else ''}")
        logger.info(f"Window size: {request.window_size}, Step size: {request.step_size}, Top N: {request.top_n}")
        
        # Get documents from database
        documents = database.get_documents_by_ids(request.doc_ids)
        
        if not documents:
            raise HTTPException(status_code=401, detail="No documents found for the provided doc_ids")
        
        logger.info(f"Found {len(documents)} documents in database")
        
        query_text = request.query
        if not request.call_api:
            # use default sorting of request.similarities if provided
            return RerankResponse(
                document_scores=[
                    DocumentScore(
                        doc_id=str(doc['doc_id']),
                        title=doc['title'],
                        url=doc['url'],
                        similarity_score=request.similarities[i] if request.similarities else 0.0,
                        original_similarity=request.similarities[i] if request.similarities else 0.0
                    ) for i, doc in enumerate(documents)
                ],
                top_windows= [WindowScore(
                    text=doc['text'][:200],  # Use first 200 chars as snippet
                    similarity_score=request.similarities[i] if request.similarities else 0.0,
                    doc_id=str(doc['doc_id']),
                    title=doc['title'],
                    window_index=0  # No specific window index since we're not using sliding windows
                ) for i, doc in enumerate(documents)],
                total_documents=len(documents),
                total_windows=0
            )
        
        # Apply rate limiting for query embedding if enabled
        if config.get('rate_limiting', {}).get('enabled', False) and rate_limiter:
            await rate_limiter.acquire()
        
        # Get query embedding
        query_embedding = await asyncio.to_thread(get_embedding, query_text)
        
        # Process documents and collect all windows
        all_windows = []  # will keep (doc_id, window_text, window_id)
        total_windows = 0
        for idx, doc in enumerate(documents):
            logger.debug(f"Processing document: {doc['doc_id']}")    
            # Tokenize document without special tokens initially
            doc_tokens = tokenize_text(f"{doc['title']} {doc['text']}", add_special_tokens=False)
            # Create sliding windows
            windows = create_sliding_windows(doc_tokens, request.window_size, request.step_size)
            total_windows += len(windows)
            # Convert windows back to text
            window_texts = prepare_window_texts(windows)
            # Add windows with metadata
            for i, window_text in enumerate(window_texts):
                all_windows.append({
                    'doc_id': doc['doc_id'], 
                    'text': window_text, 
                    'window_id': i,
                    'title': doc['title'],
                    'url': doc['url'],
                    'original_similarity': request.similarities[idx] if request.similarities else None
                })
        
        logger.debug(f"Created {len(all_windows)} windows")
        
        # Process all windows in batches to get embeddings
        await process_windows_batched(all_windows)
        
        # Calculate similarities and prepare results
        document_scores = []
        window_scores = []
        doc_max_similarities = {}  # Track max similarity per document
        
        for window in all_windows:
            # Calculate similarity between query and window
            similarity = calculate_similarity(query_embedding, window['embedding'])
            
            # Track max similarity for each document with early window boost
            doc_id = str(window['doc_id'])
            window_index = window['window_id']
            
            # Apply position-based boost: earlier windows get higher weight
            # First window (title area) gets full boost, subsequent windows get progressively less
            decay_factor = config['sliding_window']['position_boost_decay']
            position_boost = 1.0 / (1.0 + window_index * decay_factor)
            boosted_similarity = similarity * position_boost
            
            if doc_id not in doc_max_similarities:
                doc_max_similarities[doc_id] = boosted_similarity
            else:
                doc_max_similarities[doc_id] = max(doc_max_similarities[doc_id], boosted_similarity)
            
            # Create window score object
            window_scores.append(WindowScore(
                text=window.get('text', 'Unknown'),
                similarity_score=boosted_similarity,
                doc_id=str(window['doc_id']),  # Convert to string for Pydantic model
                title=window.get('title', 'Unknown'),
                window_index=window['window_id']
            ))

        # Create document scores using max similarity per document
        for idx, doc in enumerate(documents):
    
            max_similarity = doc_max_similarities[str(doc['doc_id'])]  # Use string doc_id for lookup
            document_scores.append(DocumentScore(
                doc_id=str(doc['doc_id']),  # Convert to string for Pydantic model
                title=doc.get('title', ''),
                url=doc.get('url', ''),
                similarity_score=max_similarity,
                original_similarity= request.similarities[idx] if request.similarities else None
            ))
        
        # Sort documents by similarity score (descending)
        document_scores.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Get top N windows
        window_scores.sort(key=lambda x: x.similarity_score, reverse=True)
        top_windows = window_scores[:request.top_n]
        
        logger.info(f"Reranking completed. Top document: {document_scores[0].doc_id} ({document_scores[0].similarity_score:.4f})")
        
        return RerankResponse(
            document_scores=document_scores,
            top_windows=top_windows,
            total_documents=len(documents),
            total_windows=total_windows
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
