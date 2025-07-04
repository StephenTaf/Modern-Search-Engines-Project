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
    bm25 = BM25(duckdb.connect(db_path))
    embedder = TextEmbedder(db_path, embedding_model=cfg.EMBEDDING_MODEL)
    
    
    indexer_instance = indexer.Indexer(bm25=bm25, embedder=embedder, db_path=db_path)
    logging.info(f"Indexer initialized successfully in {time.time() - _tik:.2f} seconds.")
    # Index documents
    indexer_instance.index_documents(batch_size=cfg.DEFAULT_BATCH_SIZE, embedding_batch_size=cfg.DEFAULT_EMBEDDING_BATCH_SIZE,) 
    logging.info(f"Document indexing completed successfully in {time.time() - _tik:.2f} seconds.")
    # Initialize the retriever
    retriever_instance = Retriever(bm25, embedder, indexer_instance, db_path)

    
    print("\nSearch Engine Ready. Type your query (or 'exit' to quit):\n")
    while True:
        query = input(">> ").strip()
        if query.lower() in {"exit", "quit"}:
            print("Exiting search engine.")
            break
        results = retriever_instance.search(query, top_k=10)
        if not results:
            print("No results found.")
        else:
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['title']} (Score: {result['max_score']:.3f})")
                print(f"   URL: {result['url']}")
                print(f"   Matching sentences: {result['matching_sentences']}")
                print(f"   Best sentence: {result['best_sentences'][0]['sentence'][:200]}...")
                print(f"   BM25 Score: {result['best_sentences'][0]['bm25_score']:.3f}\n embedding Score: {result['best_sentences'][0]['embedding_score']:.3f}")


        
if __name__ == "__main__":
    main()