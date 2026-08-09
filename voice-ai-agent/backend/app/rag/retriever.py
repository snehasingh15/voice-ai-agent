from typing import List
from ..db.mongo import get_knowledge_collection
from .embeddings import embed_text


def retrieve_relevant_chunks(query: str, top_k: int = 3) -> List[str]:
    """Embed the query and run an Atlas vector search, returning chunk texts."""
    coll = get_knowledge_collection()
    vec = embed_text(query)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": vec,
                "numCandidates": 100,
                "limit": top_k,
            }
        },
        {"$project": {"text": 1, "source": 1, "score": {"$meta": "vectorSearchScore"}}},
    ]

    docs = list(coll.aggregate(pipeline))
    return [d.get("text", "") for d in docs]
