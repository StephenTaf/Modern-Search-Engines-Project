from retriever import Retriever
from indexer.bm25 import BM25
from indexer.embedder import TextEmbedder
import config as cfg
from indexer import indexer
import logging
import duckdb
import time

db_path = cfg.DB_PATH
logging.basicConfig(level=logging.INFO)


def main():
    _tik = time.time()
    logging.info("Starting the search engine...")
    # Initialize the embedder and BM25
    embedder = TextEmbedder(db_path, embedding_model=cfg.EMBEDDING_MODEL)
    
    if cfg.USE_BM25:
        bm25 = BM25(duckdb.connect(db_path))
        bm25.fit()
        logging.info("BM25 initialized successfully.")
    
    
    indexer_instance = indexer.Indexer(embedder=embedder, db_path=db_path)
    logging.info(f"Indexer initialized successfully in {time.time() - _tik:.2f} seconds.")
    # Index documents
    indexer_instance.index_documents(batch_size=cfg.DEFAULT_BATCH_SIZE, embedding_batch_size=cfg.DEFAULT_EMBEDDING_BATCH_SIZE,force_reindex=False) 
    logging.info(f"Document indexing completed successfully in {time.time() - _tik:.2f} seconds.")
    # Initialize the retriever
    retriever_instance = Retriever(embedder, indexer_instance, db_path)

    
    print("\nSearch Engine Ready. Type your query (or 'exit' to quit):\n")
    while True:
        query = input(">> ").strip()
        if query.lower() in {"exit", "quit"}:
            print("Exiting search engine.")
            break
        results = retriever_instance.quick_search(query, top_k=10, return_unique_docs=True)
        if not results:
            print("No results found.")
        else:
            for i, result in enumerate(results, 1):
                 
                print(f"\n{i}. {result['title'][:50]} (Score: {result['similarity']:.3f})")
                print(f"   URL: {result['url']}")
                print(f"   Best chunk: {result['sentence'][:200]}...")
                print(f"   Document ID: {result['doc_id']}")
                print(f"   Text: {result['text'].replace('\n','')[:100]}...")


        
if __name__ == "__main__":
    main()