from datetime import datetime

from ..db.mongo import get_db


def get_caller_memory(caller_id: str) -> str | None:
    if not caller_id:
        return None
    coll = get_db().get_collection("caller_memory")
    doc = coll.find_one({"caller_id": caller_id})
    if not doc:
        return None
    return doc.get("summary")


def save_caller_memory(caller_id: str, summary: str) -> None:
    if not caller_id or summary is None:
        return
    coll = get_db().get_collection("caller_memory")
    coll.update_one(
        {"caller_id": caller_id},
        {
            "$set": {
                "summary": summary,
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
