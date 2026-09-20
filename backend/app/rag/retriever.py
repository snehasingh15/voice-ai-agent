from typing import Any, List
from pathlib import Path
import re
from ..db.mongo import get_knowledge_collection
from .embeddings import embed_text


def _ensure_knowledge_loaded():
    """Ensure knowledge base has documents loaded; if empty, ingest local markdown documents."""
    coll = get_knowledge_collection()
    try:
        if coll.count_documents({}) > 0:
            return
    except Exception:
        return

    kb_dir = Path(__file__).resolve().parents[2] / "knowledge_base"
    if not kb_dir.exists():
        return

    from .ingest import chunk_text
    docs = []
    for f in list(kb_dir.glob("*.md")) + list(kb_dir.glob("*.txt")):
        try:
            content = f.read_text(encoding="utf-8")
            chunks = chunk_text(content)
            for idx, c in enumerate(chunks):
                emb = embed_text(c)
                docs.append({
                    "text": c,
                    "embedding": emb,
                    "source": f.name,
                    "chunk_index": idx,
                    "metadata": {"auto_seeded": True},
                })
        except Exception as e:
            print(f"[rag][auto-seed] Error reading {f.name}: {e}")

    if docs:
        try:
            coll.insert_many(docs)
            print(f"[rag][auto-seed] Ingested {len(docs)} chunks into knowledge_base")
        except Exception as e:
            print(f"[rag][auto-seed] Insert failed: {e}")


def retrieve_relevant_documents(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    """Embed query, run vector or ranked keyword search across knowledge base, return scored results."""
    _ensure_knowledge_loaded()
    coll = get_knowledge_collection()
    query_str = (query or "").strip()
    if not query_str:
        return []

    # 1. Try MongoDB Atlas Vector Search
    vec = embed_text(query_str)
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": vec,
                "numCandidates": 50,
                "limit": top_k,
            }
        },
        {"$project": {"text": 1, "source": 1, "metadata": 1, "score": {"$meta": "vectorSearchScore"}}},
    ]

    docs = []
    try:
        docs = list(coll.aggregate(pipeline))
    except Exception:
        # Atlas vectorSearch index not configured or in local mode
        docs = []

    # 2. Ranked Keyword & Semantic Fallback Search
    if not docs:
        # Extract meaningful search terms (ignore stop words)
        stop_words = {"what", "when", "where", "which", "who", "whom", "this", "that", "these", "those", "have", "has", "does", "about", "with", "from"}
        raw_words = re.findall(r"\w+", query_str.lower())
        words = [w for w in raw_words if len(w) >= 3 and w not in stop_words]
        
        all_docs = []
        try:
            all_docs = list(coll.find({}, {"text": 1, "source": 1, "metadata": 1}).limit(200))
        except Exception as e:
            print(f"[rag] Failed to fetch documents from DB: {e}")

        # If DB query failed or is empty, read directly from local files
        if not all_docs:
            kb_dir = Path(__file__).resolve().parents[2] / "knowledge_base"
            if kb_dir.exists():
                from .ingest import chunk_text
                for f in kb_dir.glob("*.md"):
                    try:
                        content = f.read_text(encoding="utf-8")
                        for c in chunk_text(content):
                            all_docs.append({"text": c, "source": f.name, "metadata": {}})
                    except Exception:
                        pass

        # Score each chunk based on term frequency and query phrase proximity
        scored_docs = []
        for doc in all_docs:
            text = doc.get("text", "")
            text_lower = text.lower()
            score = 0.0

            # Exact full phrase match boost
            if query_str.lower() in text_lower:
                score += 3.0

            # Individual word matches
            for word in words:
                count = text_lower.count(word)
                if count > 0:
                    score += 1.0 + min(count * 0.2, 1.0)

            if score > 0 or not words:
                doc_copy = dict(doc)
                doc_copy["score"] = round(min(score / (len(words) + 2.0), 0.98), 3) if words else 0.5
                scored_docs.append(doc_copy)

        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        docs = scored_docs[:top_k]

    return [
        {
            "text": d.get("text", ""),
            "source": d.get("source", "knowledge_base"),
            "score": float(d.get("score", 0.0) or 0.0),
            "metadata": d.get("metadata", {}),
        }
        for d in docs
    ]


def retrieve_relevant_chunks(query: str, top_k: int = 4) -> List[str]:
    """Retrieve relevant chunks as plain strings for LLM context injection."""
    return [doc.get("text", "") for doc in retrieve_relevant_documents(query, top_k)]
