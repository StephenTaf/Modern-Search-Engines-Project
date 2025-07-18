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
import uuid
import re
from urllib.parse import urlparse
import httpx
import asyncio
import os
from pathlib import Path

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
        async with httpx.AsyncClient(timeout=cfg.RERANKER_TIMEOUT) as client:
            response = await client.post(
                f"{cfg.RERANKER_API_URL}",
                json=rerank_request_json
            )
            reranked_results = response.json()
            # await client.aclose()
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
        # TODO: ADD this back when LLM API is ready
        # top_windows = reranked_results.get('top_windows', [])
        # if top_windows:
        #     llm_request = {
        #         "most_relevant_windows": [window.get('text', '') for window in top_windows[:5]],
        #         "query": query
        #     }
        #     async with httpx.AsyncClient(timeout=cfg.RERANKER_TIMEOUT) as client:
        #         response = await client.post(
        #             f"{cfg.LLM_API_URL}",
        #             json=llm_request
        #         )
        #         llm_response = response.json()
        
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
    
    
@app.route('/api/batch_search', methods=['POST'])
async def batch_search():
    """
    Batch search endpoint that reads queries from queries.txt file and produces results
    according to format:
    - Input: queries.txt with format "query_num<tab>query_text" per line
    - Output: results with format "query_num<tab>rank<tab>url<tab>score" per line
    """
    try:
        # Look for queries.txt in the project root
        queries_file = Path(__file__).parent / 'queries.txt'
        
        if not queries_file.exists():
            return jsonify({'error': 'queries.txt file not found'}), 404
            
        if not retriever_instance:
            return jsonify({'error': 'Search engine not initialized'}), 500
        
        # Read queries from file in the specified format: query_num<tab>query_text
        queries = []
        with open(queries_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                # Split by tab to get query number and query text
                parts = line.split('\t')
                if len(parts) >= 2:
                    query_num = parts[0].strip()
                    query_text = parts[1].strip()
                    queries.append((query_num, query_text))
                else:
                    logging.warning(f"Invalid format in queries.txt line {line_num}: {line}")
        
        if not queries:
            return jsonify({'error': 'No valid queries found in queries.txt'}), 400
        
        logging.info(f"Processing {len(queries)} queries from queries.txt")
        
        # Process queries in parallel
        async def process_single_query(query_num, query_text):
            """Process a single query and return results"""
            try:
                _tik = time.time()
                
                # Preprocess query
                processed_query = preprocess_query(query_text)
                
                # Get search results
                results = retriever_instance.quick_search(
                    processed_query, 
                    top_k=cfg.TOP_K_RETRIEVAL,
                    return_unique_docs=True
                )
                
                if not results:
                    logging.info(f"No results found for query {query_num}: '{query_text}'")
                    return []
                
                # Prepare rerank request
                rerank_request_json = {
                    "doc_ids": [str(result['doc_id']) for result in results],
                    "query": processed_query,
                    "similarities": [result['similarity'] for result in results],
                    "call_api": True
                }
                
                logging.info(f"Reranking {len(results)} results for query {query_num}: '{query_text}'")
                
                # Make reranker API call in a non-blocking way
                async with httpx.AsyncClient(timeout=cfg.RERANKER_TIMEOUT) as client:
                    response = await client.post(
                        f"{cfg.RERANKER_API_URL}",
                        json=rerank_request_json
                    )
                    reranked_results = response.json()
                
                # Format results
                query_results = []
                for rank, document in enumerate(
                    reranked_results.get('document_scores', []), 
                    start=1
                ):
                    url = document.get('url', '')
                    score = document.get('similarity_score', 0.0)
                    
                    result_entry = {
                        'query_num': query_num,
                        'rank': rank,
                        'url': url,
                        'score': f"{score:.3f}",
                        'formatted_line': f"{query_num}\t{rank}\t{url}\t{score:.3f}"
                    }
                    query_results.append(result_entry)
                
                logging.info(f"Processed query {query_num}: '{query_text}' in {time.time() - _tik:.2f}s")
                return query_results
                
            except Exception as e:
                logging.error(f"Error processing query {query_num} '{query_text}': {str(e)}")
                return []
        
        # Process all queries in parallel using asyncio.gather
        _batch_tik = time.time()
        tasks = [process_single_query(query_num, query_text) for query_num, query_text in queries]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results and handle exceptions
        all_results = []
        for i, results in enumerate(results_list):
            if isinstance(results, Exception):
                logging.error(f"Exception in query {queries[i][0]}: {results}")
            else:
                all_results.extend(results)
        
        
        response_data = {
            'total_queries': len(queries),
            'total_results': len(all_results),
            'results': all_results,
            'queries_processed': [{'query_num': qn, 'query_text': qt} for qn, qt in queries],
            'processing_time': f"{time.time() - _batch_tik:.2f}s"
        }
        
        logging.info(f"Batch search completed: {len(queries)} queries, {len(all_results)} total results in {time.time() - _batch_tik:.2f}s")
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Batch search error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route('/api/batch_search_file', methods=['POST'])
async def batch_search_to_file():
    """
    Batch search endpoint that saves results to a file in the format:
    query_num<tab>rank<tab>url<tab>score per line
    """
    try:
        _tik = time.time()
        # Get results from batch search
        batch_results = await batch_search()
        
        if batch_results.status_code != 200:
            return batch_results
        
        results_data = batch_results.get_json()
        
        # Save to file in the specified format
        output_file = Path(__file__).parent / 'batch_search_results.txt'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for result in results_data['results']:
                # Write in format: query_num<tab>rank<tab>url<tab>score
                f.write(result['formatted_line'] + '\n')

        logging.info(f"Batch search results saved to {output_file} in {time.time() - _tik:.2f}s")

        return jsonify({
            'message': f'Results saved to {output_file}',
            'total_queries': results_data['total_queries'],
            'total_results': results_data['total_results'],
            'output_file': str(output_file),
            'format': 'query_num<tab>rank<tab>url<tab>score per line'
        })
        
    except Exception as e:
        logging.error(f"Batch search to file error: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

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
