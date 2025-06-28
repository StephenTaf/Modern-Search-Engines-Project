# from query_processing.models.bm25 import BM25Model
from query_processing.models.boolean import BooleanModel
from query_processing.models.core import Document, InvertedIndex
# from query_processing.models.tfidf import TfidfModel

# -------------------------------- collection -------------------------------
docs = [
    Document(
        "D1",
        "Tübingen is a traditional university town in central Baden-Württemberg."
    ),
    Document(
        "D2",
        "The University of Tübingen is one of eleven German Excellence Universities."
    ),
    Document(
        "D3",
        "Tübingen's historic old town has many narrow alleys and picturesque houses."
    ),
]

idx = InvertedIndex()
for d in docs:
    idx.add_document(d)

# -------------------------------- queries -----------------------------------
query = "university town Tübingen"

print("Boolean:", BooleanModel(idx).score(query))
# print("TF-IDF :", TfidfModel(idx).score(query))
# print("BM25   :", BM25Model(idx).score(query))
