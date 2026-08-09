import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.mongo import get_knowledge_collection
from app.rag.embeddings import embed_text


def chunk_text(text: str, target_words: int = 250):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_words = 0
    for p in paragraphs:
        words = p.split()
        wcount = len(words)
        if current_words + wcount > target_words and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_words = wcount
        else:
            current.append(p)
            current_words += wcount
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def run_ingest(knowledge_dir: Path = None):
    if knowledge_dir is None:
        knowledge_dir = Path(__file__).resolve().parents[2] / "knowledge_base"
    coll = get_knowledge_collection()
    try:
        print(f"Clearing collection {coll.name}")
        coll.delete_many({})
    except Exception as exc:
        print(f"Failed to clear collection: {exc}")
        return
    total = 0
    for md in Path(knowledge_dir).glob("*.md"):
        text = md.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        docs = []
        for c in chunks:
            try:
                emb = embed_text(c)
            except Exception as exc:
                print(f"Embedding failed for chunk from {md.name}: {exc}")
                continue
            docs.append({"text": c, "embedding": emb, "source": md.name})
        if docs:
            coll.insert_many(docs)
            total += len(docs)
    print(f"Inserted {total} chunks into knowledge_base")


if __name__ == "__main__":
    run_ingest()
