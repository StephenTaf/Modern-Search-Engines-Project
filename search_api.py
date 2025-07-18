from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from retriever import Retriever
from indexer.bm25 import BM25
from indexer.embedder import TextEmbedder
import config as cfg
from indexer import indexer
import logging
import duckdb
import time
import json
# from reranker.reranker_api import rerank, RerankRequest
import requests
import uuid
import re
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)  


logging.basicConfig(level=logging.INFO)

# Global variables for the search components
retriever_instance = None
indexer_instance = None
embedder = None
db_path = cfg.DB_PATH
if not db_path:
    logging.error("Database path is not set in config.py. Please set DB_PATH.")
db_conn = duckdb.connect(db_path, read_only=True)

def initialize_search_engine():
    """Initialize the search engine components"""
    global retriever_instance, indexer_instance, embedder, db_conn
    
    # Check if already initialized to prevent double initialization
    if retriever_instance is not None:
        logging.info("Search engine already initialized, skipping...")
        return True
    
    try:
        _tik = time.time()
        logging.info("Starting the search engine...")
        
        # Initialize the embedder (required for enforcing ANN search in duckdb)
        embedder = TextEmbedder(cfg.DB_PATH, embedding_model=cfg.EMBEDDING_MODEL, read_only=True)
        
        if cfg.USE_BM25:
            bm25 = BM25(duckdb.connect(cfg.DB_PATH))
            bm25.fit()
            logging.info("BM25 initialized successfully.")
        
        indexer_instance = indexer.Indexer(embedder=embedder, db_path=cfg.DB_PATH, read_only=True)
        logging.info(f"Indexer initialized successfully in {time.time() - _tik:.2f} seconds.")
      
        logging.info(f"Document indexing completed successfully in {time.time() - _tik:.2f} seconds.")
        # Initialize the retriever
        retriever_instance = Retriever(embedder=embedder, indexer=indexer_instance, db_path=cfg.DB_PATH)
        
        logging.info("Search engine initialized successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Failed to initialize search engine: {str(e)}")
        return False

@app.route('/api/search', methods=['POST'])
async def search():
    """Search endpoint that returns results in the format expected by the UI"""
    try:
        _tik = time.time()
        if not retriever_instance:
            return jsonify({'error': 'Search engine not initialized'}), 500
            
        data = request.get_json()
        query = data.get('query', '').strip()
        top_k = data.get('top_k', cfg.TOP_K_RETRIEVAL)  
        
        query = preprocess_query(query)
        query_id = data.get('query_id', uuid.uuid4().hex)  # Unique ID for the query
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
            
        results = retriever_instance.quick_search(query, top_k=top_k, return_unique_docs=True)
        logging.info((f"Retrieved {len(results)} results for query: {query} in {time.time() - _tik:.2f} seconds"))
    
        rerank_request_json = {
            "doc_ids": [str(result['doc_id']) for result in results],
            "query": query,
            "similarities": [result['similarity'] for result in results] if results else None,
            "call_api": True
        }
        reranked_results = requests.post(
            f"{cfg.RERANKER_API_URL}/rerank",
            json=rerank_request_json,
            timeout=cfg.RERANKER_TIMEOUT
        )
        reranked_results = reranked_results.json()
        logging.info(f"Reranked {len(reranked_results.get('document_scores', []))} results for query: {query} in {time.time() - _tik:.2f} seconds")
        if not reranked_results:
            return jsonify([])
            
        # Transform results to match the UI format
        formatted_results = []
        for i, (document, chunk) in enumerate(zip(reranked_results.get('document_scores', []), reranked_results.get('top_windows', [])), start=1):
            # Extract domain-based topic from URL
            url = document.get('url', '') 
            domain_topic = extract_domain_topic(url)

            title_text = document.get('title', '') 
            content_text = chunk.get('text', '')

            score = document.get('similarity_score', 0.0)

            formatted_result = {
                'query_id': query_id,  
                'rank': i,
                'url': url,
                'score': score,
                'title': title_text or 'No Title',
                'snippet': (content_text[:200] + '...' if len(content_text) > 200 else content_text) or 'No content available',
                'topic': domain_topic,
                'doc_id': document.get('doc_id'),
                'topics': [domain_topic],
                'primaryTopic': domain_topic,
                'secondaryTopics': []
            }
            formatted_results.append(formatted_result)

        logging.info(f"Search completed for {query} in {time.time() - _tik:.2f} seconds")
        return jsonify(formatted_results)
        
    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def preprocess_query(query: str) -> str:
    """Preprocess the query string for better search results"""
    # Basic preprocessing: strip whitespace, convert to lowercase
    # replace tuebingen with tübingen
    query = query.strip().lower()
    if "tuebingen" in query or "tubingen" in query or "tübingen" in query:
        query = query.replace('tuebingen', 'tübingen').replace('tubingen', 'tübingen')
    else:
        # If not present, we add it to the query to get more Tübingen-related results
        query = f"{query} tübingen"
    query = query.replace('tuebingen', 'tübingen').replace('tubingen', 'tübingen')
    return query.strip().lower()

def extract_domain_topic(url):
    """Extract domain-based topic from URL"""
    
    if not url or url == '#':
        return 'unknown'
    
    try:
        # Parse the URL to get the domain
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Remove www. prefix if present
        domain = re.sub(r'^www\.', '', domain)
        
        # Extract the main domain name (remove subdomains and TLD)
        # Split by dots and take the second-to-last part (main domain)
        parts = domain.split('.')
        if len(parts) >= 2:
            # For domains like uni-tuebingen.de, take the full relevant part
            if len(parts) == 2:
                main_domain = parts[0]
            else:
                # For subdomains, we try to get the meaningful part
                main_domain = parts[-2]  
        else:
            main_domain = domain
        
        # Clean up domain name for display
        main_domain = re.sub(r'[^a-zA-Z0-9-]', '', main_domain)
        return main_domain if main_domain else 'unknown'
        
    except Exception as e:
        logging.warning(f"Error extracting domain from URL {url}: {e}")
        return 'unknown'

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'search_engine_ready': retriever_instance is not None
    })

@app.route('/', methods=['GET'])
def index():
    """Serve the main UI page"""
    return render_template('index.html')

if __name__ == '__main__':
    # Initialize search engine on startup
    if initialize_search_engine():
        print("Search API server starting on http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    else:
        print("Failed to initialize search engine. Exiting.")
        exit(1)
