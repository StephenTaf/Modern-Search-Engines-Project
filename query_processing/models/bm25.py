from collections import defaultdict
from typing import Dict, List, Tuple

from .base import RetrievalModel
from .core import tokenize


class BM25Model(RetrievalModel):
    """
    Okapi BM25 (Robertson & Walker, 1994).

    Parameters
    ----------
    k1 : float
        Slope parameter (TF saturation).
    b : float
        Length-normalisation parameter.
    """

    def __init__(self, index, k1: float = 1.5, b: float = 0.75):
        super().__init__(index)
        self.k1 = k1
        self.b = b

    def score(self, query: str, k: int | None = None) -> List[Tuple[str, float]]:
        avg_len = self.index.avg_doc_len()
        q_terms = tokenize(query)

        scores: Dict[str, float] = defaultdict(float)
        for term in q_terms:
            idf = self.index.idf(term)
            for doc_id, tf in self.index.postings.get(term, []):
                doc_len = self.index.doc_len[doc_id]
                denom = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_len)
                scores[doc_id] += idf * (tf * (self.k1 + 1)) / denom

        return self._top(scores, k)
