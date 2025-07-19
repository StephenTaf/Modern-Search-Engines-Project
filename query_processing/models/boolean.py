"""
BooleanModel
===========================
Aspect ----------------------- Notes
Idea ----------------------- Treat each query term as a set filter: retrieve only docs that satisfy the Boolean expression (AND, OR, NOT).
Score ----------------------- Traditionally “binary” (1 = match, 0 = no match). In practice you may break ties by doc-length or publication date.
Complexity ----------------------- O(#postings merged). Very fast if sets are stored in skip-lists.
Strengths ----------------------- • Precise control for expert users (e.g., legislation search).
                                  • No parameter tuning.
                                  • Works even without term statistics.
Limitations	----------------------- • No ranking nuance: every match is equally relevant.
                                    • Query formulation can be painful for casual users.
Typical Uses ----------------------- Rule-based filters (“title:university AND year:2025”), de-duplicating candidate pools before a ranking stage.

"""

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
