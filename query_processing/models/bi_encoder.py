"""
(off-line)
docs.jsonl ──► embed() ──► ndarray 100×768
                            │
                            └─► FAISS Index (FlatIP or HNSW)
                                       ▲
(run-time)                   query_embedding = embed(query)
                                       │
                          top_k = FAISS.search(query_embedding, k)



1. Encode each document once → obtain a fixed-size vector (e.g. 384 or 768 floats).
2. Encode a query at run-time.
3. Return the k documents whose vectors have the highest cosine similarity to the query vector (via FAISS / Annoy / ScaNN).
"""



"""
Neural bi-encoder retrieval with optional GPU acceleration
===========================================================
Wraps a Sentence-Transformers checkpoint + FAISS ANN index.  If a CUDA‐
capable PyTorch + faiss-gpu are installed **and** ``use_gpu=True`` (the
default), *all heavy lifting* is pushed onto the GPU; otherwise the
class transparently falls back to CPU.

Usage
-----
from query_processing.core import Document
from query_processing.bi_encoder import BiEncoderModel

docs  = [Document("D1", "text …"), …]
model = BiEncoderModel(docs, model_name="bge-base-en-v1.5", use_gpu=True)
results = model.score("the query", k=10)

CUDA requirements
-----------------
• Install a CUDA-enabled PyTorch wheel (e.g. ``torch==2.3.0+cu121``).
• ``pip install faiss-gpu`` (or conda).  The code will still import if
  only *faiss-cpu* is available, but GPU mode will be disabled.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import torch

# ---------------------------------------------------------------------
# Try GPU FAISS first, fall back to CPU implementation
# ---------------------------------------------------------------------
try:
    import faiss  # noqa: F401 – imported for side-effect of availability check
    _FAISS_GPU_AVAILABLE = hasattr(faiss, "StandardGpuResources")
except ImportError:  # pragma: no cover
    raise ImportError(
        "faiss or faiss-gpu is required; install via 'pip install faiss-gpu' "
        "or 'faiss-cpu' if GPU not needed."
    )

from sentence_transformers import SentenceTransformer  # heavy import but cached

from .core import Document


class BiEncoderModel:
    """Bidirectional-encoder dense retrieval.

    Parameters
    ----------
    docs : list of Document
        Corpus to embed and index.
    model_name : str
        HuggingFace / Sentence-Transformers model ID.
    use_gpu : bool, default=True
        If *True* and CUDA + faiss-gpu are available, index & encoding
        run on GPU device 0.  Falls back silently to CPU otherwise.
    use_hnsw : bool, default=False
        Build an HNSW  (approximate) index instead of exact flat IP.
    """

    def __init__(
        self,
        docs: List[Document],
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        *,
        use_gpu: bool = True,
        use_hnsw: bool = False,
    ) -> None:
        self.docs = docs

        # ---------------------------- Encoder ----------------------------
        device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=device)

        # -------------------------- Embeddings ---------------------------
        corpus_text = [d.text.replace("\n", " ") for d in docs]
        corpus_vecs: np.ndarray = self.model.encode(
            corpus_text,
            batch_size=64,
            convert_to_numpy=True,
            normalize_embeddings=True,  # cosine ≡ inner product
            show_progress_bar=True,
        ).astype("float32")

        dim = int(corpus_vecs.shape[1])

        # ---------------------------- Index ------------------------------
        if use_hnsw:
            index_cpu = faiss.IndexHNSWFlat(dim, 32)
        else:
            index_cpu = faiss.IndexFlatIP(dim)  # exact search

        # GPU off-load if available and wanted
        if device == "cuda" and _FAISS_GPU_AVAILABLE:
            res = faiss.StandardGpuResources()
            self.index = faiss.index_cpu_to_gpu(res, 0, index_cpu)
        else:
            self.index = index_cpu

        # finally add vectors (FAISS copies to device internally)
        self.index.add(corpus_vecs)

    # ------------------------------------------------------------------ API
    def score(self, query: str, k: int | None = 10) -> List[Tuple[str, float]]:
        """Return *descending* (doc_id, score) list for *query*."""
        q_vec: np.ndarray = self.model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        ).astype("float32")

        scores, idxs = self.index.search(q_vec, k or len(self.docs))
        # FAISS already returns sorted by inner-product (== cosine)
        return [
            (self.docs[int(idx)].doc_id, float(score))
            for score, idx in zip(scores[0], idxs[0])
        ]