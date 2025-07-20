from retriever import Retriever
from indexer.bm25_indexer import BM25
from indexer.embedder import TextEmbedder
import config as cfg
from indexer import indexer
import logging
import duckdb
import time

db_path = cfg.DB_PATH 
logging.basicConfig(level=logging.INFO)
read_only = False  # Set to False to allow writing to the database

def main():
    _tik = time.time()
    logging.info("Starting the indexing process...")
    # Initialize the embedder and BM25
    embedder = TextEmbedder(db_path, embedding_model=cfg.EMBEDDING_MODEL, read_only=read_only)
    
    if cfg.USE_BM25:
        bm25 = BM25(db_path, read_only=read_only)
        bm25.build_index()
        logging.info("BM25 initialized successfully.")
    
    
    indexer_instance = indexer.Indexer(embedder=embedder, db_path=db_path, read_only=read_only)
    logging.info(f"Indexer initialized successfully in {time.time() - _tik:.2f} seconds.")
    # Index documents
    indexer_instance.index_documents(batch_size=cfg.DEFAULT_DB_FETCH_BATCH_SIZE, embedding_batch_size=cfg.DEFAULT_EMBEDDING_BATCH_SIZE,force_reindex=False) 
    logging.info(f"Document indexing completed successfully in {time.time() - _tik:.2f} seconds.")
    
    
    # Initialize the retriever
    # retriever_instance = Retriever(embedder, indexer_instance, db_path)

    
    # print("\nSearch Engine Ready. Type your query (or 'exit' to quit):\n")
    # while True:
    #     query = input(">> ").strip()
    #     if query.lower() in {"exit", "quit"}:
    #         print("Exiting search engine.")
    #         break
    #     results = retriever_instance.quick_search(query, top_k=cfg.TOP_K_RETRIEVAL, return_unique_docs=True)
    #     if not results:
    #         print("No results found.")
    #     else:
    #         for i, result in enumerate(results, 1):
                 
    #             print(f"\n{i}. {result['title'][:50]} (Score: {result['similarity']:.3f})")
    #             print(f"   URL: {result['url']}")
    #             print(f"   Best chunk: {result['sentence'][:200]}...")
    #             print(f"   Document ID: {result['doc_id']}")
    #             print(f"   Text: {result['text'].replace('\n','')[:100]}...")


        
if __name__ == "__main__":
    main()