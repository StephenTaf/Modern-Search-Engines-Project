# Document Reranker API

A FastAPI-based web service that reranks text documents based on semantic similarity to a query using sliding window embeddings. The API works with a database of documents and processes them by document IDs with optimized batched embeddings for maximum efficiency.

## Features
- Uses our pretrained model
- Can be easily changed to use remote API calls
- Windows embeddings are precomputed for better efficiency
- Uses domain control (see details in out report)
- Uses weighted BM25 score and similarity
- Uses min-max scale to have comparable scores
