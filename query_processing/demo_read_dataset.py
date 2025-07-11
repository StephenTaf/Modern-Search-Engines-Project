"""
demo_read_dataset.py – run a simple query over the 100-doc mock corpus.

Usage:  python demo_read_dataset.py "query is written here"
"""
import json
import sys
from query_processing.models.core import Document, InvertedIndex
from query_processing.models.bm25 import BM25Model

# ------------------------- load corpus from file --------------------------
DOCFILE = "dataset/mock_tuebingen_docs.jsonl"

index = InvertedIndex()
with open(DOCFILE, encoding="utf-8") as fh:
    for line in fh:
        rec = json.loads(line)
        index.add_document(Document(rec["doc_id"], rec["text"]))

# ------------------------- run a query & rank -----------------------------
query = sys.argv[1] if len(sys.argv) > 1 else "university town Tübingen"
bm25 = BM25Model(index)

results = bm25.score(query, k=20)          # already sorted high→low
print(f"Top results for: “{query}”")
for rank, (doc_id, score) in enumerate(results, 1):
    print(f"{rank:2d}. {doc_id}  {score:.4f}")
