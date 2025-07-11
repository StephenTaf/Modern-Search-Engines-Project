import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple


# --------------------------------------------------------------------------- #
#  Tokenisation                                                               #
# --------------------------------------------------------------------------- #
def tokenize(text: str) -> List[str]:
    """Very small regex tokenizer – swap for spaCy in production."""
    return re.findall(r"[A-Za-z]+", text.lower())


# --------------------------------------------------------------------------- #
#  Document / Inverted-Index                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class Document:
    doc_id: str
    text: str

    @property
    def terms(self) -> List[str]:
        return tokenize(self.text)


class InvertedIndex:
    """
    In-memory inverted index (sufficient for coursework-sized collections).
    Stores TFs, DFs, doc lengths, N, and exposes an Okapi-style IDF.
    """

    def __init__(self) -> None:
        self.postings: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self.doc_len: Dict[str, int] = {}
        self.df: Dict[str, int] = defaultdict(int)
        self.N: int = 0

    # ------------------------------ building --------------------------------
    def add_document(self, doc: Document) -> None:
        self.N += 1
        tf_counter = Counter(doc.terms)
        self.doc_len[doc.doc_id] = len(doc.terms)
        for term, tf in tf_counter.items():
            self.postings[term].append((doc.doc_id, tf))
            self.df[term] += 1

    # ---------------------------- statistics --------------------------------
    def idf(self, term: str, smoothing: float = 0.5) -> float:
        df = self.df.get(term, 0)
        return math.log(((self.N - df + smoothing) / (df + smoothing)) + 1.0)

    def avg_doc_len(self) -> float:
        return sum(self.doc_len.values()) / max(self.N, 1)
