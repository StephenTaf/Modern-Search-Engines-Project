#!/usr/bin/env python
# demo_pointwise_ltr.py
#
# Train and test the Point-wise Learning-to-Rank model over the mock corpus.
# ---------------------------------------------------------------------

import json
from query_processing.models.core import Document, InvertedIndex
from query_processing.models.bm25 import BM25Model
from query_processing.models.pointwise_ltr import PointwiseLTR

# ------------------------------------------------------------------ 1. load corpus
DOCFILE = "dataset/mock_tuebingen_docs.jsonl"
index = InvertedIndex()
with open(DOCFILE, encoding="utf-8") as fh:
    for line in fh:
        rec = json.loads(line)
        index.add_document(Document(rec["doc_id"], rec["text"]))

# ------------------------------------------------------------------ 2. synthetic relevance labels
# A real system would read qrels; here we fabricate a tiny set so the
# script is runnable out-of-the-box.

train_data = [
    # (query, doc_id, relevance_grade)
    ("university tübingen",      "D001", 3),
    ("university tübingen",      "D002", 2),
    ("university tübingen",      "D050", 0),

    ("colourful façades neckar", "D004", 3),
    ("colourful façades neckar", "D030", 2),
    ("colourful façades neckar", "D076", 0),

    ("stocherkahn race",         "D007", 3),
    ("stocherkahn race",         "D011", 2),
    ("stocherkahn race",         "D090", 0),
]

queries_docs = [(q, d) for q, d, _ in train_data]
labels        = [r      for _, _, r in train_data]

# ------------------------------------------------------------------ 3. train Pointwise LTR
ltr = PointwiseLTR(index)
ltr.fit(queries_docs, labels)

# ------------------------------------------------------------------ 4. evaluate on a new query
test_query = "cafés on the neckar river"
results = ltr.score(test_query, k=10)

print(f"Pointwise LTR results for: “{test_query}”")
for rank, (doc_id, score) in enumerate(results, 1):
    print(f"{rank:2d}. {doc_id}   {score:.4f}")
