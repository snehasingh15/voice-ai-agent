from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .config import GROQ_MODELS, TELEPHONY_PROVIDER
from .db.mongo import get_db


CONFIG_ID = "default"

DEFAULT_AGENT_CONFIG: dict[str, Any] = {
    "llm": {
        "provider": "groq",
        "model": (GROQ_MODELS.split(",")[0].strip() if GROQ_MODELS else "openai/gpt-oss-20b"),
        "temperature": 0.2,
        "max_tokens": 450,
        "reasoning_effort": "low",
    },
    "stt": {
        "provider": "deepgram",
        "model": "nova-3",
        "language": "multi",
        "keywords": "",
        "context": "",
        "endpointing_ms": 800,
    },
    "tts": {
        "provider": "edge",
        "model": "edge-tts",
        "voice": "en-US-AriaNeural",
        "speed": 1.0,
        "stability": 0.5,
    },
    "calling": {
        "telephony_provider": TELEPHONY_PROVIDER or "exotel",
        "ambient_noise": "none",
        "noise_cancellation_percent": 100,
        "voicemail_detection_seconds": 2.5,
        "dtmf_enabled": False,
        "auto_reschedule": False,
        "inbound_enabled": True,
        "total_call_timeout_seconds": 2400,
        "user_online_detection": True,
        "user_online_message": "Hello, are you still on the line?",
        "final_call_message": "Thank you for your time. Goodbye.",
        "hangup_on_silence_seconds": 18,
        "allow_interruption": True,
    },
    "tools": {
        "calendar_availability": True,
        "book_appointment": True,
        "transfer_call": True,
        "knowledge_base": True,
    },
    "extractions": {
        "enabled": True,
        "fields": ["name", "intent", "appointment_date", "callback_number", "sentiment"],
    },
    "webhooks": {
        "enabled": False,
        "url": "",
        "events": ["call.completed", "extraction.created", "handoff.created"],
    },
    "graph": {
        "start_node": "triage",
        "nodes": [
            {
                "id": "triage",
                "name": "Triage",
                "instruction": "Classify intent and route to booking, support, billing, or handoff.",
                "routes": [
                    {"contains": ["appointment", "doctor", "book"], "target": "booking"},
                    {"contains": ["bill", "payment", "refund"], "target": "billing"},
                    {"contains": ["human", "agent", "manager"], "target": "handoff"},
                ],
                "fallback": "support",
            },
            {"id": "booking", "name": "Booking Agent", "instruction": "Use calendar tools and collect patient details.", "routes": [], "fallback": "handoff"},
            {"id": "support", "name": "Support Agent", "instruction": "Answer from knowledge base and ask clarifying questions.", "routes": [], "fallback": "handoff"},
            {"id": "billing", "name": "Billing Agent", "instruction": "Collect billing intent and escalate sensitive payment issues.", "routes": [], "fallback": "handoff"},
            {"id": "handoff", "name": "Human Handoff", "instruction": "Create a handoff request with a concise summary.", "routes": [], "fallback": None},
        ],
    },
    "squads": {
        "enabled": True,
        "active": "default-squad",
        "members": ["triage", "booking", "support", "handoff"],
    },
    "testing": {
        "qa_scoring_enabled": True,
        "regression_messages": [
            "I want to book a doctor appointment tomorrow",
            "My internet is not working and I want to talk to a human",
        ],
    },
}


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (updates or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def get_agent_config() -> dict[str, Any]:
    config = deepcopy(DEFAULT_AGENT_CONFIG)
    try:
        doc = get_db().get_collection("agent_configurations").find_one({"_id": CONFIG_ID}) or {}
        config = _deep_merge(config, {k: v for k, v in doc.items() if k not in {"_id", "updatedAt"}})
    except Exception as exc:
        print(f"[agent-config][warning] using defaults: {exc}")
    return config


def save_agent_config(updates: dict[str, Any]) -> dict[str, Any]:
    config = _deep_merge(get_agent_config(), updates or {})
    config["updatedAt"] = datetime.now(timezone.utc)
    try:
        get_db().get_collection("agent_configurations").update_one(
            {"_id": CONFIG_ID},
            {"$set": config},
            upsert=True,
        )
    except Exception as exc:
        raise RuntimeError(f"Could not save agent configuration: {exc}") from exc
    return get_agent_config()


def get_configured_llm() -> dict[str, Any]:
    return get_agent_config().get("llm", DEFAULT_AGENT_CONFIG["llm"])


def get_configured_stt() -> dict[str, Any]:
    return get_agent_config().get("stt", DEFAULT_AGENT_CONFIG["stt"])


def get_configured_tts() -> dict[str, Any]:
    return get_agent_config().get("tts", DEFAULT_AGENT_CONFIG["tts"])
