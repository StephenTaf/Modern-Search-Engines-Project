import math
from collections import Counter
from typing import Dict, List, Tuple

from .base import RetrievalModel
from .core import tokenize


class TfidfModel(RetrievalModel):
    """
    Classic TF-IDF with cosine normalisation.
    Note: for brevity we recompute document vectors on-the-fly.
    """

    def score(self, query: str, k: int | None = None) -> List[Tuple[str, float]]:
        q_terms = tokenize(query)
        q_tf = Counter(q_terms)
        q_vec = {t: tf * self.index.idf(t) for t, tf in q_tf.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values()))

        scores: Dict[str, float] = {}
        for term, q_w in q_vec.items():
            idf = self.index.idf(term)
            for doc_id, tf in self.index.postings.get(term, []):
                scores[doc_id] = scores.get(doc_id, 0.0) + q_w * tf * idf

        for doc_id, numer in list(scores.items()):
            # recompute doc vector norm
            vec = {
                t: tf * self.index.idf(t)
                for t, tf in Counter(self._doc_terms(doc_id)).items()
            }
            d_norm = math.sqrt(sum(v * v for v in vec.values()))
            if d_norm * q_norm:
                scores[doc_id] = numer / (d_norm * q_norm)

        return self._top(scores, k)

    # ---------- helper: retrieve doc terms (only needed for this demo) ------
    def _doc_terms(self, doc_id: str) -> List[str]:
        # In production, terms would be fetched from storage; the demo uses
        # the index’s postings to rebuild them.
        terms: List[str] = []
        for t, pl in self.index.postings.items():
            for d_id, tf in pl:
                if d_id == doc_id:
                    terms.extend([t] * tf)
        return terms
