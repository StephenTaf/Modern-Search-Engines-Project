from __future__ import annotations

from typing import Dict, List, Tuple


class RetrievalModel:
    """
    Abstract base class for all ranking functions.
    Subclasses override `score`.
    """

    def __init__(self, index):
        self.index = index

    # --------------------------- public API ----------------------------------
    def score(self, query: str, k: int | None = None) -> List[Tuple[str, float]]:
        raise NotImplementedError

    # ------------------------- convenience ----------------------------------
    def _top(self, scores: Dict[str, float], k: int | None) -> List[Tuple[str, float]]:
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[: k or len(ranked)]
