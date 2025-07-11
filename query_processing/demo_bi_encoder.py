"""demo_bi_encoder.py – GPU‑aware mini‑demo
===========================================
Reads the *mock_tuebingen_docs.jsonl* corpus, builds a ``BiEncoderModel``
(with GPU if available) and prints the top‑10 most similar documents.

Run:
    $ python demo_bi_encoder.py "stocherkahn race"  --cpu
    $ python demo_bi_encoder.py "cafés on the neckar river"

Flags:
    --cpu   Force CPU mode even if CUDA + faiss‑gpu are available.
"""

import argparse
import json
from pathlib import Path

from query_processing.models.core import Document
from query_processing.models.bi_encoder import BiEncoderModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Bi‑encoder search demo")
    parser.add_argument("query", help="Query string")
    parser.add_argument("--docfile", default="dataset/mock_tuebingen_docs.jsonl")
    parser.add_argument("--cpu", action="store_true", help="Force CPU mode")
    parser.add_argument("-k", type=int, default=10, help="Number of hits")
    args = parser.parse_args()

    # ------------------------- load corpus -------------------------
    docs = []
    with open(Path(args.docfile), encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            docs.append(Document(rec["doc_id"], rec["text"]))

    # ----------------------- build + search ------------------------
    model = BiEncoderModel(docs, use_gpu=not args.cpu)
    hits = model.score(args.query, k=args.k)

    # --------------------------- print -----------------------------
    print(f"Bi‑encoder results for: “{args.query}” (k={args.k})")
    for rank, (doc_id, score) in enumerate(hits, 1):
        print(f"{rank:2d}. {doc_id}  {score:.4f}")


if __name__ == "__main__":
    main()
