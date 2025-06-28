from typing import List, Tuple

from .base import RetrievalModel
from .core import tokenize


class BooleanModel(RetrievalModel):
    """
    Simple AND Boolean retrieval: returns docs that contain *all* query terms.
    """

    def score(self, query: str, k: int | None = None) -> List[Tuple[str, float]]:
        terms = set(tokenize(query))
        if not terms:
            return []

        candidate_sets = [
            {doc_id for doc_id, _ in self.index.postings.get(t, [])} for t in terms
        ]
        common = set.intersection(*candidate_sets) if candidate_sets else set()
        return [(doc_id, 1.0) for doc_id in list(common)[: k or len(common)]]
