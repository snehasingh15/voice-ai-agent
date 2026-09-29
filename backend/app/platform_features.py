from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests

from .agent_config import get_agent_config
from .db.mongo import get_db


PROVIDER_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "llm": [
        {"id": "groq", "name": "Groq", "status": "wired", "models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "groq/compound-mini"]},
        {"id": "gemini", "name": "Google Gemini", "status": "fallback", "models": ["gemini-flash-latest", "gemini-2.5-flash"]},
        {"id": "openai", "name": "OpenAI", "status": "planned", "models": ["gpt-4.1-mini", "gpt-4o-mini"]},
        {"id": "azure", "name": "Azure OpenAI", "status": "planned", "models": []},
    ],
    "stt": [
        {"id": "deepgram", "name": "Deepgram", "status": "wired", "models": ["nova-3", "nova-2"]},
        {"id": "openai", "name": "OpenAI Transcribe", "status": "planned", "models": ["gpt-4o-transcribe"]},
        {"id": "assemblyai", "name": "AssemblyAI", "status": "planned", "models": []},
        {"id": "azure", "name": "Azure Speech", "status": "planned", "models": []},
        {"id": "google", "name": "Google Speech", "status": "planned", "models": []},
        {"id": "sarvam", "name": "Sarvam", "status": "planned", "models": []},
        {"id": "soniox", "name": "Soniox", "status": "planned", "models": []},
    ],
    "tts": [
        {"id": "edge", "name": "Edge TTS", "status": "wired", "models": ["edge-tts"]},
        {"id": "elevenlabs", "name": "ElevenLabs", "status": "planned", "models": ["eleven_turbo_v2_5"]},
        {"id": "openai", "name": "OpenAI Audio", "status": "planned", "models": ["gpt-4o-mini-tts"]},
        {"id": "cartesia", "name": "Cartesia", "status": "planned", "models": []},
        {"id": "rime", "name": "Rime", "status": "planned", "models": []},
        {"id": "polly", "name": "Amazon Polly", "status": "planned", "models": []},
    ],
    "telephony": [
        {"id": "exotel", "name": "Exotel", "status": "wired"},
        {"id": "twilio", "name": "Twilio", "status": "wired"},
        {"id": "plivo", "name": "Plivo", "status": "planned"},
        {"id": "sip_trunk", "name": "SIP Trunk", "status": "planned"},
        {"id": "freeswitch", "name": "FreeSwitch", "status": "planned"},
        {"id": "vobiz", "name": "Vobiz", "status": "planned"},
    ],
}


DEFAULT_AGENT_GRAPH = {
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
}



PLATFORM_STATUS: dict[str, list[dict[str, str]]] = {
    "runtime_features": [
        {"feature": "Real-time streaming STT/TTS pipeline", "status": "partial", "notes": "Browser uses turn-based chunks; telephony websocket streams media frames but STT is still finalized per utterance."},
        {"feature": "Barge-in/interruption engine", "status": "partial", "notes": "Interruption config exists; full cancel/drain behavior still needs live audio task cancellation."},
        {"feature": "Turn finalization and silence detection", "status": "partial", "notes": "Exotel silence/RMS turn finalization exists; mark/ack state machine is not complete."},
        {"feature": "Language detection and live switching", "status": "partial", "notes": "Language config and provider model support exist; automatic live LID/switching is pending."},
        {"feature": "Provider adapters", "status": "partial", "notes": "Registry and config exist; Groq/Gemini/Deepgram/Edge are wired, other SDKs need keys and adapter implementations."},
        {"feature": "Telephony providers", "status": "partial", "notes": "Twilio and Exotel are wired; Plivo/SIP/FreeSwitch/Vobiz are registered but pending full media handlers."},
        {"feature": "Graph-based agent routing", "status": "implemented", "notes": "Configurable graph/pathway router and route preview API are implemented."},
        {"feature": "Extraction agents", "status": "implemented", "notes": "Configured fields are extracted and persisted to MongoDB."},
        {"feature": "Webhook agents", "status": "implemented", "notes": "Optional secured webhook dispatch exists for call/test events."},
        {"feature": "Voicemail detection", "status": "partial", "notes": "Config exists; real audio classifier is pending."},
        {"feature": "Audio mark/ack tracking", "status": "partial", "notes": "Foundation exists in telephony logs; provider-specific playout mark tracking is pending."},
        {"feature": "Handoff/transfer handling", "status": "partial", "notes": "Handoff requests exist; live provider transfer per carrier is pending."},
        {"feature": "Production test suite", "status": "partial", "notes": "Existing tests plus simulation runner; provider-scale websocket and carrier tests are pending."},
    ],
    "platform_capabilities": [
        {"feature": "Developer-first voice agents", "status": "implemented", "notes": "API docs, provider registry, config UI, and Platform Lab are present."},
        {"feature": "Provider choice across STT/LLM/TTS", "status": "partial", "notes": "Provider/model UI is dynamic; not every provider is runtime-wired."},
        {"feature": "Web + phone deployment", "status": "partial", "notes": "Browser console, Twilio, and Exotel paths exist; more carriers pending."},
        {"feature": "Tool/API integrations", "status": "implemented", "notes": "Tool calls, RAG, webhooks, calendar/booking tools are present."},
        {"feature": "Low-latency conversations", "status": "partial", "notes": "Metrics and websocket exist; true streaming STT/LLM/TTS remains pending."},
        {"feature": "Multi-assistant squads", "status": "partial", "notes": "Squad config and graph routing exist; runtime specialist handoff can be expanded."},
        {"feature": "Visual conversation builder", "status": "partial", "notes": "Graph JSON editor and preview exist; drag-and-drop builder pending."},
        {"feature": "Simulation and regression tests", "status": "implemented", "notes": "Platform Lab can run regression simulations and stores results."},
        {"feature": "A/B analytics", "status": "partial", "notes": "Prompt versions and analytics exist; experiment assignment/reporting pending."},
        {"feature": "QA/call scoring", "status": "implemented", "notes": "QA scoring API and Platform Lab scorer exist."},
        {"feature": "Batch tests", "status": "implemented", "notes": "Regression messages run as a batch simulation."},
        {"feature": "GitHub sync", "status": "pending", "notes": "No GitHub integration yet."},
        {"feature": "Voice library/voice cloning", "status": "partial", "notes": "Voice/model selection exists; cloning requires provider SDK and consent controls."},
        {"feature": "Usage analytics", "status": "implemented", "notes": "Call logs, latency, token metrics, tool usage, and simulations are stored."},
        {"feature": "200+ integrations / CRM", "status": "partial", "notes": "Webhook foundation exists; marketplace-style integration catalog pending."},
        {"feature": "Collaborative design", "status": "pending", "notes": "No multi-user collaboration layer yet."},
        {"feature": "Knowledge bases/actions/tools", "status": "implemented", "notes": "RAG, prompt lab, and tools are present."},
    ],
}


def get_platform_status() -> dict[str, list[dict[str, str]]]:
    return PLATFORM_STATUS
def get_provider_registry() -> dict[str, list[dict[str, Any]]]:
    return PROVIDER_REGISTRY


def get_agent_graph() -> dict[str, Any]:
    config = get_agent_config()
    return config.get("graph") or DEFAULT_AGENT_GRAPH


def route_with_graph(message: str, graph: dict[str, Any] | None = None) -> dict[str, Any]:
    graph = graph or get_agent_graph()
    nodes = {node.get("id"): node for node in graph.get("nodes", [])}
    current_id = graph.get("start_node") or "triage"
    text = (message or "").lower()
    visited: list[str] = []

    for _ in range(8):
        node = nodes.get(current_id)
        if not node:
            break
        visited.append(current_id)
        next_id = None
        for route in node.get("routes", []):
            keywords = [str(item).lower() for item in route.get("contains", [])]
            if any(keyword in text for keyword in keywords):
                next_id = route.get("target")
                break
        if not next_id:
            next_id = node.get("fallback")
        if not next_id or next_id == current_id or next_id not in nodes:
            return {"node": node, "path": visited, "reason": "matched" if len(visited) > 1 else "fallback"}
        current_id = next_id

    node = nodes.get(current_id) or nodes.get(graph.get("start_node")) or {}
    return {"node": node, "path": visited, "reason": "max_depth"}


def _sentiment(text: str) -> str:
    lower = (text or "").lower()
    if any(word in lower for word in ["angry", "bad", "terrible", "cancel", "complaint", "not working"]):
        return "negative"
    if any(word in lower for word in ["thanks", "good", "great", "perfect", "helpful"]):
        return "positive"
    return "neutral"


def extract_conversation_fields(caller_id: str, session_id: str, transcript: str, reply_text: str) -> dict[str, Any]:
    config = get_agent_config().get("extractions", {})
    if not config.get("enabled", True):
        return {}

    text = f"{transcript or ''}\n{reply_text or ''}"
    fields = config.get("fields") or []
    extracted: dict[str, Any] = {}

    phone_match = re.search(r"(\+?\d[\d\s-]{8,}\d)", text)
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|today|tomorrow)\b", text, re.I)
    name_match = re.search(r"(?:my name is|i am|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)

    for field in fields:
        if field == "callback_number" and phone_match:
            extracted[field] = phone_match.group(1).strip()
        elif field == "appointment_date" and date_match:
            extracted[field] = date_match.group(1)
        elif field == "name" and name_match:
            extracted[field] = name_match.group(1)
        elif field == "sentiment":
            extracted[field] = _sentiment(text)
        elif field == "intent":
            extracted[field] = route_with_graph(text).get("node", {}).get("id", "support")

    doc = {
        "caller_id": caller_id,
        "session_id": session_id,
        "fields": extracted,
        "transcript": transcript,
        "reply_text": reply_text,
        "createdAt": datetime.now(timezone.utc),
    }
    try:
        get_db().get_collection("conversation_extractions").insert_one(doc)
    except Exception as exc:
        print(f"[extractions][warning] failed to persist: {exc}")
    return extracted


def maybe_dispatch_webhook(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    webhook_config = get_agent_config().get("webhooks", {})
    if not webhook_config.get("enabled"):
        return {"sent": False, "reason": "disabled"}
    url = (webhook_config.get("url") or "").strip()
    if not url:
        return {"sent": False, "reason": "missing_url"}

    event_payload = {
        "event": event_type,
        "payload": payload,
        "sentAt": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response = requests.post(url, json=event_payload, timeout=8)
        result = {"sent": True, "status_code": response.status_code}
    except Exception as exc:
        result = {"sent": False, "reason": str(exc)}

    try:
        get_db().get_collection("webhook_events").insert_one({
            "event": event_type,
            "payload": payload,
            "result": result,
            "createdAt": datetime.now(timezone.utc),
        })
    except Exception:
        pass
    return result


def score_call_quality(transcript: str, reply_text: str, latency_ms: float = 0) -> dict[str, Any]:
    transcript = transcript or ""
    reply_text = reply_text or ""
    checks = {
        "has_user_input": bool(transcript.strip()),
        "has_agent_reply": bool(reply_text.strip()),
        "not_too_verbose": len(reply_text.split()) <= 120,
        "low_latency": float(latency_ms or 0) <= 3500,
        "handoff_sensitive": not any(word in transcript.lower() for word in ["emergency", "legal", "suicide"]),
    }
    score = round((sum(1 for ok in checks.values() if ok) / len(checks)) * 100)
    return {
        "score": score,
        "grade": "pass" if score >= 80 else "review",
        "checks": checks,
    }


def run_simulation(messages: list[str], caller_id: str = "simulator") -> dict[str, Any]:
    from .pipeline.llm import generate_agent_reply

    history: list[dict[str, str]] = []
    turns = []
    for message in messages:
        routed = route_with_graph(message)
        reply = generate_agent_reply(message, history, used_tools=[])
        qa = score_call_quality(message, reply)
        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ])
        turns.append({
            "user": message,
            "reply": reply,
            "route": routed.get("node", {}).get("id"),
            "path": routed.get("path", []),
            "qa": qa,
        })

    doc = {
        "caller_id": caller_id,
        "messages": messages,
        "turns": turns,
        "average_score": round(sum(turn["qa"]["score"] for turn in turns) / max(1, len(turns))),
        "createdAt": datetime.now(timezone.utc),
    }
    try:
        result = get_db().get_collection("simulation_runs").insert_one(doc)
        doc["_id"] = str(result.inserted_id)
    except Exception:
        doc["_id"] = "not-persisted"
    return doc
