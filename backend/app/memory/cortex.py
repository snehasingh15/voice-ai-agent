from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..db.mongo import get_db


DEFAULT_MEMORY_POLICY = {
    "enabled": True,
    "save_language": "en",
    "do_not_store_patterns": [
        "password",
        "otp",
        "one time password",
        "credit card",
        "cvv",
        "secret",
        "api key",
    ],
    "store_tone_and_speech": True,
    "store_semantic_facts": True,
    "store_episodic_events": True,
    "store_procedural_preferences": True,
    "max_retrieved_items": 8,
}


MEMORY_COLLECTIONS = {
    "policy": "memory_orchestration_policies",
    "cells": "memory_storage_cells",
    "events": "memory_events",
    "profile": "customer_memory_profiles",
    "audit": "memory_audit_log",
}


def _now():
    return datetime.now(timezone.utc)


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in doc.items():
        if key == "_id":
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def get_memory_policy(tenant_id: str = "default") -> dict[str, Any]:
    try:
        doc = get_db().get_collection(MEMORY_COLLECTIONS["policy"]).find_one({"tenant_id": tenant_id}) or {}
        return {**DEFAULT_MEMORY_POLICY, **{k: v for k, v in doc.items() if k not in {"_id", "tenant_id", "updatedAt"}}}
    except Exception:
        return dict(DEFAULT_MEMORY_POLICY)


def save_memory_policy(policy: dict[str, Any], tenant_id: str = "default") -> dict[str, Any]:
    merged = {**DEFAULT_MEMORY_POLICY, **(policy or {}), "tenant_id": tenant_id, "updatedAt": _now()}
    get_db().get_collection(MEMORY_COLLECTIONS["policy"]).update_one(
        {"tenant_id": tenant_id},
        {"$set": merged},
        upsert=True,
    )
    return get_memory_policy(tenant_id)


def _blocked_by_policy(text: str, policy: dict[str, Any]) -> tuple[bool, str | None]:
    lower = (text or "").lower()
    for pattern in policy.get("do_not_store_patterns", []):
        if pattern and str(pattern).lower() in lower:
            return True, str(pattern)
    return False, None


def _tone(text: str) -> str:
    lower = (text or "").lower()
    if any(word in lower for word in ["angry", "upset", "bad", "complaint", "not working"]):
        return "frustrated"
    if any(word in lower for word in ["thanks", "thank you", "great", "good"]):
        return "positive"
    return "neutral"


def _extract_semantic_facts(text: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if not text:
        return facts
    name = re.search(r"(?:my name is|i am|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    city = re.search(r"(?:i live in|from|located in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    age = re.search(r"\b(?:i am|age is)\s+(\d{1,3})\b", text, re.I)
    language = re.search(r"\b(?:speak|language is|prefer)\s+(hindi|english|tamil|telugu|kannada|marathi|bengali)\b", text, re.I)
    if name:
        facts.append({"key": "name", "value": name.group(1), "confidence": 0.82})
    if city:
        facts.append({"key": "location", "value": city.group(1), "confidence": 0.7})
    if age:
        facts.append({"key": "age", "value": age.group(1), "confidence": 0.75})
    if language:
        facts.append({"key": "preferred_language", "value": language.group(1).lower(), "confidence": 0.76})
    return facts


def _extract_procedures(text: str) -> list[dict[str, Any]]:
    lower = (text or "").lower()
    procedures = []
    if "call me" in lower or "callback" in lower:
        procedures.append({"key": "contact_procedure", "value": "Offer callback and confirm phone number.", "confidence": 0.7})
    if "hindi" in lower:
        procedures.append({"key": "conversation_procedure", "value": "Prefer Hindi or Hinglish when caller uses Hindi.", "confidence": 0.68})
    if "human" in lower or "manager" in lower:
        procedures.append({"key": "handoff_procedure", "value": "Escalate to human handoff when caller explicitly requests a person.", "confidence": 0.78})
    return procedures


def ingest_memory_turn(
    caller_id: str,
    session_id: str,
    transcript: str,
    reply_text: str,
    tenant_id: str = "default",
    channel: str = "voice",
) -> dict[str, Any]:
    policy = get_memory_policy(tenant_id)
    text = f"{transcript or ''}\n{reply_text or ''}".strip()
    if not policy.get("enabled", True) or not caller_id or not text:
        return {"stored": False, "reason": "disabled_or_empty"}

    blocked, reason = _blocked_by_policy(text, policy)
    audit = {
        "tenant_id": tenant_id,
        "caller_id": caller_id,
        "session_id": session_id,
        "channel": channel,
        "action": "blocked" if blocked else "ingested",
        "reason": reason,
        "createdAt": _now(),
    }
    get_db().get_collection(MEMORY_COLLECTIONS["audit"]).insert_one(audit)
    if blocked:
        return {"stored": False, "reason": f"blocked_by_policy:{reason}"}

    cells = []
    if policy.get("store_episodic_events", True):
        cells.append({
            "memory_type": "episodic",
            "content": transcript,
            "metadata": {"reply": reply_text, "channel": channel, "tone": _tone(transcript) if policy.get("store_tone_and_speech", True) else None},
        })

    if policy.get("store_semantic_facts", True):
        for fact in _extract_semantic_facts(text):
            cells.append({"memory_type": "semantic", "content": f"{fact['key']}: {fact['value']}", "metadata": fact})

    if policy.get("store_procedural_preferences", True):
        for procedure in _extract_procedures(text):
            cells.append({"memory_type": "procedural", "content": procedure["value"], "metadata": procedure})

    coll = get_db().get_collection(MEMORY_COLLECTIONS["cells"])
    now = _now()
    stored = []
    for cell in cells:
        doc = {
            "tenant_id": tenant_id,
            "caller_id": caller_id,
            "session_id": session_id,
            "memory_type": cell["memory_type"],
            "content": cell["content"],
            "metadata": cell.get("metadata") or {},
            "language": policy.get("save_language", "en"),
            "createdAt": now,
            "updatedAt": now,
        }
        result = coll.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        stored.append(_serialize(doc))

    _rebuild_customer_profile(caller_id, tenant_id)
    get_db().get_collection(MEMORY_COLLECTIONS["events"]).insert_one({
        "tenant_id": tenant_id,
        "caller_id": caller_id,
        "session_id": session_id,
        "stored_count": len(stored),
        "createdAt": now,
    })
    return {"stored": True, "count": len(stored), "cells": stored}


def retrieve_memory_context(caller_id: str, query: str = "", tenant_id: str = "default") -> dict[str, Any]:
    policy = get_memory_policy(tenant_id)
    limit = int(policy.get("max_retrieved_items", 8))
    try:
        cursor = get_db().get_collection(MEMORY_COLLECTIONS["cells"]).find(
            {"tenant_id": tenant_id, "caller_id": caller_id},
            {"_id": 0},
        ).sort("createdAt", -1).limit(limit)
        cells = list(cursor)
    except Exception:
        cells = []
    grouped = {"procedural": [], "semantic": [], "episodic": []}
    for cell in cells:
        grouped.setdefault(cell.get("memory_type", "episodic"), []).append(cell)
    profile = get_customer_memory_profile(caller_id, tenant_id)
    context_lines = []
    for memory_type in ["procedural", "semantic", "episodic"]:
        for cell in grouped.get(memory_type, [])[:3]:
            context_lines.append(f"{memory_type}: {cell.get('content')}")
    return {
        "caller_id": caller_id,
        "profile": profile,
        "cells": cells,
        "grouped": grouped,
        "context": "\n".join(context_lines),
    }


def _rebuild_customer_profile(caller_id: str, tenant_id: str = "default") -> None:
    cells = list(get_db().get_collection(MEMORY_COLLECTIONS["cells"]).find(
        {"tenant_id": tenant_id, "caller_id": caller_id, "memory_type": "semantic"},
        {"_id": 0, "metadata": 1},
    ).sort("createdAt", -1).limit(100))
    facts = {}
    for cell in cells:
        metadata = cell.get("metadata") or {}
        key = metadata.get("key")
        value = metadata.get("value")
        if key and value and key not in facts:
            facts[key] = value
    get_db().get_collection(MEMORY_COLLECTIONS["profile"]).update_one(
        {"tenant_id": tenant_id, "caller_id": caller_id},
        {"$set": {"tenant_id": tenant_id, "caller_id": caller_id, "facts": facts, "updatedAt": _now()}},
        upsert=True,
    )


def get_customer_memory_profile(caller_id: str, tenant_id: str = "default") -> dict[str, Any]:
    doc = get_db().get_collection(MEMORY_COLLECTIONS["profile"]).find_one({"tenant_id": tenant_id, "caller_id": caller_id}) or {
        "tenant_id": tenant_id,
        "caller_id": caller_id,
        "facts": {},
    }
    return _serialize(doc)


def list_memory_cells(caller_id: str | None = None, tenant_id: str = "default", limit: int = 100) -> list[dict[str, Any]]:
    query = {"tenant_id": tenant_id}
    if caller_id:
        query["caller_id"] = caller_id
    docs = list(get_db().get_collection(MEMORY_COLLECTIONS["cells"]).find(query).sort("createdAt", -1).limit(limit))
    return [_serialize(doc) for doc in docs]


def delete_memory_cell(memory_id: str) -> bool:
    from bson import ObjectId
    result = get_db().get_collection(MEMORY_COLLECTIONS["cells"]).delete_one({"_id": ObjectId(memory_id)})
    return result.deleted_count > 0

