"""Distributed Session Store supporting Redis / KeyDB with automatic fallback
to MongoDB Atlas persistent sessions collection with TTL (Time-To-Live).

Ensures horizontal scalability across multiple FastAPI worker processes/containers
without losing active conversation context or memory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..config import REDIS_URL
from ..db.mongo import get_db

_redis_client = None
_redis_available = None


def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client

    if not REDIS_URL:
        _redis_available = False
        return None

    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2.0)
        client.ping()
        _redis_client = client
        _redis_available = True
        print("[session_store] Connected to Redis/KeyDB distributed cache")
        return _redis_client
    except Exception as exc:
        print(f"[session_store] Redis not available ({exc}). Falling back to MongoDB TTL session store.")
        _redis_available = False
        return None


def _get_mongo_session_coll():
    db = get_db()
    coll = db.get_collection("sessions")
    # Ensure TTL index on updatedAt so old sessions expire automatically after 24 hours
    try:
        coll.create_index("updatedAt", expireAfterSeconds=86400, background=True)
    except Exception:
        pass
    return coll


def get_caller_id_from_session(session_id: str | None = None) -> str | None:
    if not session_id:
        return None
    if "|" in session_id:
        return session_id.split("|", 1)[1]
    if session_id.startswith("session-"):
        return session_id[len("session-"):]
    return session_id


def get_session_history(session_id: str | None = None) -> list[dict[str, str]]:
    """Retrieve full conversational turn history for a given session."""
    if not session_id:
        return []

    r = _get_redis()
    if r:
        try:
            raw = r.get(f"session:{session_id}")
            if raw:
                return json.loads(raw)
        except Exception as exc:
            print(f"[session_store][redis_error] {exc}")

    # Fallback to MongoDB
    try:
        coll = _get_mongo_session_coll()
        doc = coll.find_one({"session_id": session_id})
        if doc and "history" in doc:
            return doc["history"]
    except Exception as exc:
        print(f"[session_store][mongo_error] {exc}")

    return []


def set_session_history(session_id: str, history: list[dict[str, str]]) -> None:
    """Overwrite the full conversation history for a session."""
    if not session_id:
        return

    r = _get_redis()
    if r:
        try:
            r.setex(f"session:{session_id}", 86400, json.dumps(history))
        except Exception as exc:
            print(f"[session_store][redis_error] {exc}")

    try:
        coll = _get_mongo_session_coll()
        coll.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "history": history,
                    "caller_id": get_caller_id_from_session(session_id),
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception as exc:
        print(f"[session_store][mongo_error] {exc}")


def append_session_message(session_id: str, role: str, content: str) -> list[dict[str, str]]:
    """Append a single message turn (user/assistant/system) to the distributed session."""
    if not session_id or not content:
        return get_session_history(session_id)

    history = get_session_history(session_id)
    history.append({"role": role, "content": content})
    set_session_history(session_id, history)
    return history


def clear_session(session_id: str) -> None:
    """Clear session data upon explicit completion or logout."""
    if not session_id:
        return

    r = _get_redis()
    if r:
        try:
            r.delete(f"session:{session_id}")
        except Exception:
            pass

    try:
        coll = _get_mongo_session_coll()
        coll.delete_one({"session_id": session_id})
    except Exception:
        pass
