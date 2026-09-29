from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from .agent_config import get_agent_config
from .db.mongo import get_db


LANGUAGE_HINTS = {
    "hi": ["hai", "namaste", "doctor", "mujhe", "aap", "kya", "nahi", "haan", "kal"],
    "en": ["the", "hello", "book", "appointment", "support", "billing", "call", "thanks"],
}


def detect_language(text: str) -> dict[str, Any]:
    normalized = (text or "").lower()
    scores = {
        language: sum(1 for token in hints if token in normalized)
        for language, hints in LANGUAGE_HINTS.items()
    }
    language = max(scores, key=scores.get) if any(scores.values()) else "unknown"
    return {
        "language": language,
        "confidence": min(0.95, 0.45 + (scores.get(language, 0) * 0.1)) if language != "unknown" else 0.2,
        "scores": scores,
    }


def detect_voicemail(text: str = "", audio_duration_ms: int = 0, silence_ms: int = 0) -> dict[str, Any]:
    lower = (text or "").lower()
    voicemail_phrases = [
        "leave a message",
        "after the tone",
        "not available",
        "mailbox",
        "voicemail",
        "record your message",
    ]
    phrase_hit = any(phrase in lower for phrase in voicemail_phrases)
    long_silence = silence_ms >= 2500 and audio_duration_ms >= 4000
    detected = phrase_hit or long_silence
    return {
        "voicemail": detected,
        "confidence": 0.9 if phrase_hit else 0.72 if long_silence else 0.2,
        "reason": "phrase" if phrase_hit else "silence" if long_silence else "not_detected",
    }


def assign_ab_variant(experiment_id: str, subject_id: str, variants: list[str] | None = None) -> dict[str, Any]:
    variants = variants or ["A", "B"]
    digest = hashlib.sha256(f"{experiment_id}:{subject_id}".encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % max(1, len(variants))
    assignment = {
        "experiment_id": experiment_id,
        "subject_id": subject_id,
        "variant": variants[index],
        "assignedAt": datetime.now(timezone.utc),
    }
    try:
        get_db().get_collection("ab_assignments").update_one(
            {"experiment_id": experiment_id, "subject_id": subject_id},
            {"$set": assignment},
            upsert=True,
        )
    except Exception:
        pass
    return {**assignment, "assignedAt": assignment["assignedAt"].isoformat()}


def build_github_sync_payload() -> dict[str, Any]:
    config = get_agent_config()
    serializable = json.loads(json.dumps(config, default=str))
    return {
        "filename": "voice-ai-agent-config.json",
        "branch": "voice-ai-config-sync",
        "commit_message": "Sync Voice AI agent configuration",
        "content": serializable,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "note": "This creates a sync-ready payload. Pushing to GitHub requires a GitHub token/app connection.",
    }


def create_collaboration_event(payload: dict[str, Any]) -> dict[str, Any]:
    doc = {
        "target": payload.get("target") or "agent-config",
        "kind": payload.get("kind") or "comment",
        "author": payload.get("author") or "admin",
        "message": payload.get("message") or "",
        "status": payload.get("status") or "open",
        "createdAt": datetime.now(timezone.utc),
    }
    result = get_db().get_collection("collaboration_events").insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["createdAt"] = doc["createdAt"].isoformat()
    return doc


def save_voice_profile(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("type") == "clone" and not payload.get("consent_confirmed"):
        raise ValueError("Voice cloning requires explicit consent_confirmed=true.")
    doc = {
        "name": payload.get("name") or "Untitled voice",
        "provider": payload.get("provider") or "edge",
        "voice_id": payload.get("voice_id") or payload.get("voice") or "",
        "type": payload.get("type") or "stock",
        "consent_confirmed": bool(payload.get("consent_confirmed")),
        "notes": payload.get("notes") or "",
        "createdAt": datetime.now(timezone.utc),
    }
    result = get_db().get_collection("voice_profiles").insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["createdAt"] = doc["createdAt"].isoformat()
    return doc


def streaming_session_snapshot(session_id: str, state: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = {
        "session_id": session_id,
        "state": state,
        "metadata": metadata or {},
        "updatedAt": datetime.now(timezone.utc),
    }
    try:
        get_db().get_collection("streaming_sessions").update_one(
            {"session_id": session_id},
            {"$set": doc},
            upsert=True,
        )
    except Exception:
        pass
    return {**doc, "updatedAt": doc["updatedAt"].isoformat()}


def classify_transfer_intent(text: str) -> dict[str, Any]:
    lower = (text or "").lower()
    should_transfer = bool(re.search(r"\b(human|agent|manager|representative|transfer|escalate)\b", lower))
    return {
        "transfer": should_transfer,
        "target": "human_agent" if should_transfer else None,
        "reason": "explicit_request" if should_transfer else "none",
    }
