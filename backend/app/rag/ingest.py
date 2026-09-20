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


def extract_pdf_text(pdf_bytes: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages).strip()


def ingest_text(text: str, source: str, metadata: dict[str, object] | None = None, replace_source: bool = False) -> int:
    coll = get_knowledge_collection()
    if replace_source:
        coll.delete_many({"source": source})
    chunks = chunk_text(text)
    docs = []
    for idx, chunk in enumerate(chunks):
        emb = embed_text(chunk)
        docs.append({
            "text": chunk,
            "embedding": emb,
            "source": source,
            "chunk_index": idx,
            "metadata": metadata or {},
        })
    if docs:
        coll.insert_many(docs)
    return len(docs)


def run_ingest(knowledge_dir: Path | None = None):
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
    files = list(Path(knowledge_dir).glob("*.md")) + list(Path(knowledge_dir).glob("*.txt")) + list(Path(knowledge_dir).glob("*.pdf"))
    for md in files:
        if md.suffix.lower() == ".pdf":
            text = extract_pdf_text(md.read_bytes())
        else:
            text = md.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        docs = []
        for idx, c in enumerate(chunks):
            try:
                emb = embed_text(c)
            except Exception as exc:
                print(f"Embedding failed for chunk from {md.name}: {exc}")
                continue
            docs.append({"text": c, "embedding": emb, "source": md.name, "chunk_index": idx, "metadata": {"ingest_type": "bulk"}})
        if docs:
            coll.insert_many(docs)
            total += len(docs)
    print(f"Inserted {total} chunks into knowledge_base")


if __name__ == "__main__":
    run_ingest()
