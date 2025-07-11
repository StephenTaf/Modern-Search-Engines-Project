"""
PointwiseLTR
===========================
Aspect ----------------------- Notes
Idea ----------------------- Learn a regression (or ordinal-classification) function f(q,d) that predicts a graded relevance label.
In this demo ----------------------- Features = BM25 score + query length → fed into LinearRegression. We can replace with any feature set / regressor.
Workflow ----------------------- 1. Generate candidate set (e.g. top-1000 BM25).
                                 2. Compute feature vector for each (q,d).
                                 3. Train on judged data.
                                 4. At runtime, predict, then sort by f(q,d).
Strengths ----------------------- • Simple to train (MSE, logistic).
                                  • Can ingest arbitrary numeric / categorical features (pagerank, freshness, etc.).
Limitations	----------------------- • Ignores relative ordering (no pairwise or listwise loss).
                                    • Beware score-calibration drift across queries.
Good for -----------------------  feature-ablation studies, quick re-ranking when judgment set is small. We can move to pairwise/listwise or neural models when we have ≥ 10 k judged pairs.

"""


from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
from sklearn.linear_model import LinearRegression

from .base import RetrievalModel
from .bm25 import BM25Model
from .core import tokenize


class PointwiseLTR(RetrievalModel):
    """
    Simple point-wise learning-to-rank (regression) demo.
    Uses *only* BM25 + query length as features; extend as needed.
    """

    def __init__(self, index):
        super().__init__(index)
        self.model = LinearRegression()
        self.fitted = False
        # Re-use one BM25 instance for efficiency
        self._bm25 = BM25Model(index)

    # --------------------------- training -----------------------------------
    def fit(self, qd_pairs: List[Tuple[str, str]], labels: List[float]):
        X = [self._features(q, d) for q, d in qd_pairs]
        self.model.fit(np.asarray(X), np.asarray(labels))
        self.fitted = True

    # --------------------------- scoring ------------------------------------
    def score(self, query: str, k: int | None = None) -> List[Tuple[str, float]]:
        assert self.fitted, "Call `fit` with training data before scoring."
        candidate_docs = {
            doc_id
            for term in tokenize(query)
            for doc_id, _ in self.index.postings.get(term, [])
        }
        scores: Dict[str, float] = {}
        for doc_id in candidate_docs:
            scores[doc_id] = float(self.model.predict([self._features(query, doc_id)]))
        return self._top(scores, k)

    # --------------------------- features -----------------------------------
    def _features(self, query: str, doc_id: str) -> List[float]:
        bm25_score = self._bm25_single(query, doc_id)
        return [bm25_score, len(tokenize(query))]

    def _bm25_single(self, query: str, doc_id: str) -> float:
        # Score a single document with BM25 (avoid sorting all docs).
        query_terms = tokenize(query)
        score = 0.0
        avg_len = self.index.avg_doc_len()
        for term in query_terms:
            idf = self.index.idf(term)
            for d_id, tf in self.index.postings.get(term, []):
                if d_id != doc_id:
                    continue
                doc_len = self.index.doc_len[d_id]
                denom = tf + self._bm25.k1 * (
                    1 - self._bm25.b + self._bm25.b * doc_len / avg_len
                )
                score += idf * (tf * (self._bm25.k1 + 1)) / denom
        return score
