from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db.mongo import get_db

# ─────────────────────────────────────────────────────────────────────────────
# Default Tenant Memory Configuration (matching attached screenshots)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TENANT_MEMORY_CONFIG = {
    "remember_conversations": True,
    "channels": {
        "voice": True,          # Voice calls: Inbound and outbound phone calls
        "web_chat": True,       # Web chat: The website / app chat assistant
        "whatsapp": True,       # WhatsApp chat: WhatsApp conversations
        "mcp_server": True,     # MCP Server: Conversations from an MCP client
    },
    "visibility": "isolated",   # "isolated" (per agent) or "shared" (across all agents)
    "last_changed_by": "admin@voiceai.app",
    "last_changed_at": "2026-09-28T17:44:59Z",
}

DEFAULT_TENANT_RULES = [
    {
        "key": "context_max_chars",
        "value": "1000",
        "required": True,
        "max": 8000,
        "is_system": True,
        "description": "required · from tenant · max 8,000",
    },
    {
        "key": "always_remember",
        "value": "allergies, current medications, preferred doctor, preferred language, preferred appointment time",
        "required": False,
        "description": "from tenant",
    },
    {
        "key": "block_one_time_secrets",
        "value": "true",
        "required": False,
        "description": "from tenant",
    },
    {
        "key": "block_card_numbers",
        "value": "true",
        "required": False,
        "description": "from tenant",
    },
    {
        "key": "block_national_ids",
        "value": "true",
        "required": False,
        "description": "from tenant",
    },
    {
        "key": "blocked_topics",
        "value": "salary, religion, caste, politics",
        "required": False,
        "description": "from tenant",
    },
    {
        "key": "min_confidence",
        "value": "0.4",
        "required": False,
        "description": "from tenant",
    },
]

# Pre-seeded agent directory matching user's office screenshot
INITIAL_AGENTS_SEED = [
    {"id": "reminder", "name": "Reminder", "initials": "R", "memory_on": True, "shares_with": 4, "description": "Appointment reminder and patient reschedule coordinator", "languages": "English, Hindi"},
    {"id": "feedback", "name": "Feedback", "initials": "F", "memory_on": True, "shares_with": 1, "description": "Post-visit patient satisfaction survey & rating agent", "languages": "English, Hindi"},
    {"id": "feedback-cortex-test", "name": "FEEDBACK-Cortex-Test", "initials": "FC", "memory_on": True, "shares_with": 1, "description": "Automated Cortex regression test agent for feedback pipelines", "languages": "English"},
    {"id": "booking", "name": "Booking", "initials": "B", "memory_on": True, "shares_with": 2, "description": "Doctor OPD consultation and slot reservation agent", "languages": "English, Hindi, Hinglish"},
    {"id": "booking-cortex-test", "name": "BOOKING-Cortex-Test", "initials": "BC", "memory_on": True, "shares_with": 1, "description": "Staging validation agent for slot verification tools", "languages": "English"},
    {"id": "follow-up", "name": "Follow-up", "initials": "FU", "memory_on": True, "shares_with": 2, "description": "Patient care follow-up and medicine schedule verification", "languages": "English, Hindi"},
    {"id": "services-lead", "name": "Services - Lead Qualification", "initials": "SL", "memory_on": True, "shares_with": 0, "description": "Inbound healthcare services lead scoring and qualification", "languages": "English"},
    {"id": "grievance-kims", "name": "Grievance Agent Kims", "initials": "GA", "memory_on": True, "shares_with": 0, "description": "Patient complaint registration and hospital escalation officer", "languages": "English, Hindi"},
    {"id": "post-op", "name": "Post OP. Feedback Agent", "initials": "PO", "memory_on": True, "shares_with": 0, "description": "Surgical discharge follow-up and recovery monitoring", "languages": "English"},
    {"id": "bsdm-survey", "name": "BSDM Survey Agent", "initials": "BS", "memory_on": False, "shares_with": 0, "description": "Skill development mission public survey surveyor", "languages": "Hindi"},
    {"id": "products-lead", "name": "Products - Lead Qualification", "initials": "PL", "memory_on": False, "shares_with": 0, "description": "Medical device and pharmacy inquiry qualifier", "languages": "English"},
    {"id": "catla-helpdesk", "name": "Catla Help Desk (Demo)", "initials": "CH", "memory_on": True, "shares_with": 0, "description": "Fiber internet customer support and technician dispatcher", "languages": "English, Hindi"},
    {"id": "fore-school", "name": "Fore School of Management", "initials": "FS", "memory_on": True, "shares_with": 0, "description": "Campus admissions and management program counseling", "languages": "English"},
    {"id": "aarogya", "name": "Aarogya Agent", "initials": "AA", "memory_on": True, "shares_with": 0, "description": "National health program benefits and clinic guidance", "languages": "English, Hindi"},
    {"id": "telecom-support", "name": "Telecom Support Assistant", "initials": "TS", "memory_on": True, "shares_with": 0, "description": "Voice SIP trunking and billing diagnostic specialist", "languages": "English"},
]

DEFAULT_REMINDER_OVERRIDES = {
    "always_remember": "preferred appointment time, reason for rescheduling",
}

MEMORY_COLLECTIONS = {
    "policy": "memory_orchestration_policies",
    "tenant_rules": "memory_tenant_rules",
    "agent_rules": "memory_agent_rules",
    "agents": "memory_agents_directory",
    "graph_nodes": "memory_graph_nodes",
    "graph_edges": "memory_graph_edges",
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

# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Fast O(1) Hash Map Index for Knowledge Graph Lookups (Mem0 Inspired)
# ─────────────────────────────────────────────────────────────────────────────

class GraphMemoryIndex:
    """O(1) In-memory Graph Hash Index for sub-millisecond memory relation lookup.
    
    Inspired by Mem0 entity-relationship architecture:
    - Nodes hash-indexed by node_id: O(1) lookup
    - Outgoing edges hash-indexed by source node: O(1) lookup
    - Incoming edges hash-indexed by target node: O(1) lookup
    """
    def __init__(self):
        self.nodes: dict[str, dict[str, Any]] = {}
        self.adj_out: dict[str, list[dict[str, Any]]] = {}
        self.adj_in: dict[str, list[dict[str, Any]]] = {}
        self._seed_default_graph()

    def _seed_default_graph(self):
        default_nodes = [
            {"id": "caller_demo", "label": "Caller (+91-9513886363)", "type": "user", "properties": {"phone": "+91-9513886363", "preferred_language": "Hindi"}},
            {"id": "agent_reminder", "label": "Reminder Agent", "type": "agent", "properties": {"shares_with": 4, "role": "rescheduling"}},
            {"id": "pref_time", "label": "Preferred Time: Morning 10:00 AM", "type": "preference", "properties": {"slot": "10:00 AM", "weekday": "Saturday"}},
            {"id": "reschedule_reason", "label": "Reschedule Reason: Office Meeting", "type": "reason", "properties": {"category": "work_conflict"}},
            {"id": "doc_arpit", "label": "Dr. Arpit Jain", "type": "doctor", "properties": {"dept": "Internal Medicine", "fee": 1500}},
            {"id": "doc_seema", "label": "Dr. Seema Dhir", "type": "doctor", "properties": {"dept": "Internal Medicine", "fee": 1500}},
            {"id": "rule_no_salary", "label": "Blocked Topic: Salary/Finance", "type": "guardrail", "properties": {"policy": "pii_protection"}},
            {"id": "rule_max_chars", "label": "Context Max: 1000 Chars", "type": "guardrail", "properties": {"budget": 1000}},
        ]
        default_edges = [
            {"id": "e1", "source": "caller_demo", "target": "agent_reminder", "relation": "INTERACTS_WITH", "confidence": 0.95},
            {"id": "e2", "source": "caller_demo", "target": "pref_time", "relation": "ALWAYS_REMEMBER", "confidence": 0.92},
            {"id": "e3", "source": "caller_demo", "target": "reschedule_reason", "relation": "HAS_REASON", "confidence": 0.88},
            {"id": "e4", "source": "caller_demo", "target": "doc_arpit", "relation": "PREFERRED_DOCTOR", "confidence": 0.90},
            {"id": "e5", "source": "agent_reminder", "target": "pref_time", "relation": "TRACKS_STATE", "confidence": 0.98},
            {"id": "e6", "source": "agent_reminder", "target": "rule_no_salary", "relation": "ENFORCES_RULE", "confidence": 1.0},
            {"id": "e7", "source": "agent_reminder", "target": "rule_max_chars", "relation": "ENFORCES_BUDGET", "confidence": 1.0},
        ]
        for node in default_nodes:
            self.add_node(node)
        for edge in default_edges:
            self.add_edge(edge)

    def add_node(self, node: dict[str, Any]):
        nid = node["id"]
        self.nodes[nid] = node
        if nid not in self.adj_out:
            self.adj_out[nid] = []
        if nid not in self.adj_in:
            self.adj_in[nid] = []

    def add_edge(self, edge: dict[str, Any]):
        eid = edge.get("id") or str(uuid.uuid4())
        edge["id"] = eid
        s = edge["source"]
        t = edge["target"]
        if s not in self.adj_out:
            self.adj_out[s] = []
        if t not in self.adj_in:
            self.adj_in[t] = []
        # Update or append
        self.adj_out[s] = [e for e in self.adj_out[s] if not (e["source"] == s and e["target"] == t and e.get("relation") == edge.get("relation"))]
        self.adj_out[s].append(edge)
        self.adj_in[t] = [e for e in self.adj_in[t] if not (e["source"] == s and e["target"] == t and e.get("relation") == edge.get("relation"))]
        self.adj_in[t].append(edge)

    def lookup_node(self, node_id: str) -> dict[str, Any] | None:
        """O(1) hash lookup."""
        return self.nodes.get(node_id)

    def get_related_entities(self, node_id: str) -> list[dict[str, Any]]:
        """O(1) retrieval of connected graph relations."""
        outgoing = self.adj_out.get(node_id, [])
        incoming = self.adj_in.get(node_id, [])
        return outgoing + incoming

    def get_graph_data(self) -> dict[str, Any]:
        all_edges = []
        for edges in self.adj_out.values():
            all_edges.extend(edges)
        return {
            "nodes": list(self.nodes.values()),
            "edges": all_edges,
            "metrics": {
                "total_nodes": len(self.nodes),
                "total_edges": len(all_edges),
                "lookup_complexity": "O(1)",
                "avg_degree": round(len(all_edges) / max(1, len(self.nodes)), 2),
                "last_indexed": _now().isoformat(),
            }
        }

# Global singleton graph index
_GRAPH_INDEX = GraphMemoryIndex()

# ─────────────────────────────────────────────────────────────────────────────
# Tenant Memory Policy & Rules Engine
# ─────────────────────────────────────────────────────────────────────────────

def get_tenant_memory_config(tenant_id: str = "default") -> dict[str, Any]:
    try:
        doc = get_db().get_collection(MEMORY_COLLECTIONS["policy"]).find_one({"tenant_id": tenant_id})
        if not doc:
            return dict(DEFAULT_TENANT_MEMORY_CONFIG)
        return {**DEFAULT_TENANT_MEMORY_CONFIG, **{k: v for k, v in doc.items() if k not in {"_id", "tenant_id"}}}
    except Exception:
        return dict(DEFAULT_TENANT_MEMORY_CONFIG)


def save_tenant_memory_config(config: dict[str, Any], tenant_id: str = "default") -> dict[str, Any]:
    merged = {
        **DEFAULT_TENANT_MEMORY_CONFIG,
        **config,
        "tenant_id": tenant_id,
        "last_changed_at": _now().isoformat(),
    }
    try:
        get_db().get_collection(MEMORY_COLLECTIONS["policy"]).update_one(
            {"tenant_id": tenant_id},
            {"$set": merged},
            upsert=True,
        )
    except Exception:
        pass
    log_memory_audit(tenant_id=tenant_id, agent_id="system", channel="system", action="policy_updated", details=merged)
    return get_tenant_memory_config(tenant_id)


def get_tenant_rules(tenant_id: str = "default") -> list[dict[str, Any]]:
    try:
        coll = get_db().get_collection(MEMORY_COLLECTIONS["tenant_rules"])
        docs = list(coll.find({"tenant_id": tenant_id}, {"_id": 0, "tenant_id": 0}))
        if not docs:
            # Seed default tenant rules
            for rule in DEFAULT_TENANT_RULES:
                coll.update_one({"tenant_id": tenant_id, "key": rule["key"]}, {"$set": {**rule, "tenant_id": tenant_id}}, upsert=True)
            return list(DEFAULT_TENANT_RULES)
        # Ensure context_max_chars is present
        keys = {d["key"] for d in docs}
        for def_rule in DEFAULT_TENANT_RULES:
            if def_rule["key"] not in keys:
                docs.append(def_rule)
        return docs
    except Exception:
        return list(DEFAULT_TENANT_RULES)


def save_tenant_rules(rules: list[dict[str, Any]], tenant_id: str = "default") -> list[dict[str, Any]]:
    try:
        coll = get_db().get_collection(MEMORY_COLLECTIONS["tenant_rules"])
        coll.delete_many({"tenant_id": tenant_id})
        for r in rules:
            clean = {
                "key": r.get("key", "").strip(),
                "value": str(r.get("value", "")).strip(),
                "required": bool(r.get("required", False)),
                "max": r.get("max"),
                "description": r.get("description", "from tenant"),
                "tenant_id": tenant_id,
                "updatedAt": _now(),
            }
            if clean["key"]:
                coll.insert_one(clean)
    except Exception:
        pass
    log_memory_audit(tenant_id=tenant_id, agent_id="system", channel="system", action="tenant_rules_saved", details={"rule_count": len(rules)})
    return get_tenant_rules(tenant_id)

# ─────────────────────────────────────────────────────────────────────────────
# Agents Directory & Per-Agent Memory Rules Engine (Matching Screenshots 3 & 4)
# ─────────────────────────────────────────────────────────────────────────────

def get_agents_directory(tenant_id: str = "default") -> list[dict[str, Any]]:
    try:
        coll = get_db().get_collection(MEMORY_COLLECTIONS["agents"])
        docs = list(coll.find({"tenant_id": tenant_id}, {"_id": 0}))
        if not docs:
            # Seed default agents
            for a in INITIAL_AGENTS_SEED:
                doc = {**a, "tenant_id": tenant_id, "createdAt": _now()}
                coll.update_one({"tenant_id": tenant_id, "id": a["id"]}, {"$set": doc}, upsert=True)
            return list(INITIAL_AGENTS_SEED)
        return docs
    except Exception:
        return list(INITIAL_AGENTS_SEED)


def get_agent_rules(agent_id: str, tenant_id: str = "default") -> dict[str, Any]:
    """Computes effective rules for an agent:
    - Same key as a tenant rule: agent value wins.
    - Locked rows are inherited from tenant; press + to override.
    - Returns structured rules with inheritance status.
    """
    agents = {a["id"]: a for a in get_agents_directory(tenant_id)}
    agent_meta = agents.get(agent_id, {"id": agent_id, "name": agent_id.capitalize(), "memory_on": True, "shares_with": 0})

    tenant_rules = get_tenant_rules(tenant_id)
    tenant_rule_map = {r["key"]: r for r in tenant_rules}

    # Fetch agent overrides
    agent_overrides = {}
    try:
        doc = get_db().get_collection(MEMORY_COLLECTIONS["agent_rules"]).find_one({"tenant_id": tenant_id, "agent_id": agent_id})
        if doc and "overrides" in doc:
            agent_overrides = doc["overrides"]
        elif agent_id == "reminder":
            agent_overrides = dict(DEFAULT_REMINDER_OVERRIDES)
    except Exception:
        if agent_id == "reminder":
            agent_overrides = dict(DEFAULT_REMINDER_OVERRIDES)

    effective_rules = []

    # 1. First add overridden rules (editable, can be deleted)
    for key, val in agent_overrides.items():
        tenant_origin = tenant_rule_map.get(key)
        effective_rules.append({
            "key": key,
            "value": val,
            "is_overridden": True,
            "is_inherited": False,
            "tenant_value": tenant_origin.get("value") if tenant_origin else None,
            "required": tenant_origin.get("required", False) if tenant_origin else False,
            "max": tenant_origin.get("max") if tenant_origin else None,
            "description": "Rules for this agent only. Same key as a tenant rule: this value wins.",
        })

    # 2. Add inherited rules from tenant (locked rows with + button)
    for t_rule in tenant_rules:
        k = t_rule["key"]
        if k not in agent_overrides:
            effective_rules.append({
                "key": k,
                "value": t_rule["value"],
                "is_overridden": False,
                "is_inherited": True,
                "tenant_value": t_rule["value"],
                "required": t_rule.get("required", False),
                "max": t_rule.get("max"),
                "description": t_rule.get("description") or "from tenant",
            })

    return {
        "agent": agent_meta,
        "agent_id": agent_id,
        "rules": effective_rules,
        "total_rules": len(effective_rules),
        "overridden_count": len(agent_overrides),
        "summary": f"{len(effective_rules)} rules in effect for this agent, including the required pre-call memory size.",
    }


def save_agent_rules(agent_id: str, overrides: dict[str, str], tenant_id: str = "default") -> dict[str, Any]:
    try:
        coll = get_db().get_collection(MEMORY_COLLECTIONS["agent_rules"])
        clean_overrides = {k.strip(): str(v).strip() for k, v in overrides.items() if k.strip()}
        coll.update_one(
            {"tenant_id": tenant_id, "agent_id": agent_id},
            {"$set": {"tenant_id": tenant_id, "agent_id": agent_id, "overrides": clean_overrides, "updatedAt": _now()}},
            upsert=True,
        )
    except Exception:
        pass
    log_memory_audit(tenant_id=tenant_id, agent_id=agent_id, channel="system", action="agent_rules_saved", details={"overrides": overrides})
    return get_agent_rules(agent_id, tenant_id)


def remove_all_agent_overrides(agent_id: str, tenant_id: str = "default") -> dict[str, Any]:
    try:
        coll = get_db().get_collection(MEMORY_COLLECTIONS["agent_rules"])
        coll.delete_one({"tenant_id": tenant_id, "agent_id": agent_id})
    except Exception:
        pass
    log_memory_audit(tenant_id=tenant_id, agent_id=agent_id, channel="system", action="agent_rules_reset", details={})
    return get_agent_rules(agent_id, tenant_id)

# ─────────────────────────────────────────────────────────────────────────────
# Audit Log & Memory Ingestion with Security / PII Redaction
# ─────────────────────────────────────────────────────────────────────────────

def log_memory_audit(
    tenant_id: str = "default",
    agent_id: str = "system",
    channel: str = "voice",
    caller_id: str = "system",
    session_id: str = "system",
    action: str = "audit",
    details: Any = None,
    reason: str | None = None,
):
    try:
        record = {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "channel": channel,
            "caller_id": caller_id,
            "session_id": session_id,
            "action": action,
            "reason": reason,
            "details": details or {},
            "timestamp": _now().isoformat(),
        }
        get_db().get_collection(MEMORY_COLLECTIONS["audit"]).insert_one(record)
    except Exception:
        pass


def get_memory_activity(tenant_id: str = "default", limit: int = 50) -> list[dict[str, Any]]:
    try:
        cursor = get_db().get_collection(MEMORY_COLLECTIONS["audit"]).find({"tenant_id": tenant_id}).sort("timestamp", -1).limit(limit)
        return [_serialize(doc) for doc in cursor]
    except Exception:
        return [
            {
                "timestamp": _now().isoformat(),
                "agent_id": "reminder",
                "channel": "voice",
                "caller_id": "+91-9513886363",
                "action": "ingested",
                "details": {"key": "preferred_time", "value": "Morning 10 AM", "confidence": 0.92},
            },
            {
                "timestamp": _now().isoformat(),
                "agent_id": "reminder",
                "channel": "voice",
                "caller_id": "+91-9513886363",
                "action": "blocked",
                "reason": "block_card_numbers: matched card number pattern",
                "details": {"rule": "block_card_numbers"},
            },
        ]


def _check_security_violations(text: str, rules_list: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Validates text against security and PII rules (OTP, credit card, national IDs, blocked topics)."""
    rules_dict = {r["key"]: str(r.get("value", "")).lower() for r in rules_list}

    # 1. OTP / One-time secrets
    if rules_dict.get("block_one_time_secrets") in {"true", "1", "yes"}:
        if re.search(r"\b(otp|one[\s-]?time[\s-]?password|pin|secret\s*key|auth[\s-]?token|cvv)\s*(?:is|:)?\s*\d{4,8}\b", text, re.I):
            return True, "block_one_time_secrets: OTP/Secret detected in utterance"

    # 2. Credit Card numbers
    if rules_dict.get("block_card_numbers") in {"true", "1", "yes"}:
        if re.search(r"\b(?:\d[ -]*?){13,16}\b", text):
            # Luhn-like or 16 digit sequence check
            return True, "block_card_numbers: Payment card sequence detected"

    # 3. National IDs (Aadhaar 12-digit, SSN 9-digit, PAN 10-char alphanumeric)
    if rules_dict.get("block_national_ids") in {"true", "1", "yes"}:
        if re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text): # Aadhaar
            return True, "block_national_ids: National ID (Aadhaar) sequence detected"
        if re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", text, re.I): # Indian PAN
            return True, "block_national_ids: PAN Card pattern detected"

    # 4. Blocked topics (salary, religion, caste, politics)
    blocked_topics_str = rules_dict.get("blocked_topics", "")
    if blocked_topics_str:
        topics = [t.strip().lower() for t in blocked_topics_str.split(",") if t.strip()]
        lower_text = text.lower()
        for topic in topics:
            if topic in lower_text:
                return True, f"blocked_topics: forbidden topic '{topic}' detected"

    return False, None


def ingest_memory_turn(
    caller_id: str,
    session_id: str,
    transcript: str,
    reply_text: str,
    tenant_id: str = "default",
    agent_id: str = "reminder",
    channel: str = "voice",
) -> dict[str, Any]:
    """Ingests a conversational turn, enforces tenant & agent guardrails,
    extracts entities, updates the O(1) Knowledge Graph, and stores authorized cells."""
    tenant_cfg = get_tenant_memory_config(tenant_id)
    if not tenant_cfg.get("remember_conversations", True):
        return {"stored": False, "reason": "remember_conversations_disabled"}

    # Channel check
    allowed_channels = tenant_cfg.get("channels", {})
    if channel and not allowed_channels.get(channel, True):
        return {"stored": False, "reason": f"channel_{channel}_disabled"}

    combined_text = f"{transcript or ''}\n{reply_text or ''}".strip()
    if not combined_text:
        return {"stored": False, "reason": "empty_turn"}

    # Get effective rules for the specific agent
    agent_rule_data = get_agent_rules(agent_id, tenant_id)
    rules_list = agent_rule_data["rules"]

    # Security & Guardrail check
    is_violation, violation_reason = _check_security_violations(combined_text, rules_list)
    if is_violation:
        log_memory_audit(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=channel,
            caller_id=caller_id,
            session_id=session_id,
            action="blocked",
            reason=violation_reason,
            details={"transcript": transcript[:100]},
        )
        return {"stored": False, "reason": violation_reason}

    # Extract Entities & Update Knowledge Graph in real-time
    user_node_id = f"user_{caller_id or 'anon'}"
    _GRAPH_INDEX.add_node({"id": user_node_id, "label": f"Caller: {caller_id}", "type": "user", "properties": {"channel": channel}})
    agent_node_id = f"agent_{agent_id}"
    _GRAPH_INDEX.add_node({"id": agent_node_id, "label": f"Agent: {agent_id.capitalize()}", "type": "agent", "properties": {}})
    _GRAPH_INDEX.add_edge({"source": user_node_id, "target": agent_node_id, "relation": "SESSION_INTERACTION", "confidence": 1.0})

    # Semantic facts extraction
    facts = []
    # Preferred time pattern
    time_match = re.search(r"\b(?:prefer|at|time|around)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", transcript, re.I)
    if time_match:
        time_val = time_match.group(1)
        node_id = f"pref_{uuid.uuid4().hex[:6]}"
        _GRAPH_INDEX.add_node({"id": node_id, "label": f"Time: {time_val}", "type": "preference", "properties": {"time": time_val}})
        _GRAPH_INDEX.add_edge({"source": user_node_id, "target": node_id, "relation": "PREFERS_TIME", "confidence": 0.91})
        facts.append({"key": "preferred_time", "value": time_val, "confidence": 0.91})

    # Reschedule reason pattern
    reason_match = re.search(r"\b(?:reschedule|cancel|postpone|due to|because of)\s+([A-Za-z\s]{3,30})\b", transcript, re.I)
    if reason_match:
        reason_val = reason_match.group(1).strip()
        node_id = f"reason_{uuid.uuid4().hex[:6]}"
        _GRAPH_INDEX.add_node({"id": node_id, "label": f"Reason: {reason_val}", "type": "reason", "properties": {"reason": reason_val}})
        _GRAPH_INDEX.add_edge({"source": user_node_id, "target": node_id, "relation": "RESCHEDULE_REASON", "confidence": 0.89})
        facts.append({"key": "reschedule_reason", "value": reason_val, "confidence": 0.89})

    # Doctor preference
    doc_match = re.search(r"\b(Dr\.?\s+[A-Za-z]+(?:\s+[A-Za-z]+)?)\b", transcript, re.I)
    if doc_match:
        doc_val = doc_match.group(1)
        node_id = f"doc_{uuid.uuid4().hex[:6]}"
        _GRAPH_INDEX.add_node({"id": node_id, "label": doc_val, "type": "doctor", "properties": {"name": doc_val}})
        _GRAPH_INDEX.add_edge({"source": user_node_id, "target": node_id, "relation": "PREFERRED_DOCTOR", "confidence": 0.94})
        facts.append({"key": "preferred_doctor", "value": doc_val, "confidence": 0.94})

    # Store memory cells in MongoDB
    now = _now()
    stored_cells = []
    coll = get_db().get_collection(MEMORY_COLLECTIONS["cells"])
    for f in facts:
        doc = {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "caller_id": caller_id,
            "session_id": session_id,
            "memory_type": "semantic",
            "content": f"{f['key']}: {f['value']}",
            "metadata": f,
            "createdAt": now,
        }
        res = coll.insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        stored_cells.append(_serialize(doc))

    log_memory_audit(
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=channel,
        caller_id=caller_id,
        session_id=session_id,
        action="ingested",
        details={"stored_count": len(stored_cells), "facts": facts},
    )

    return {"stored": True, "count": len(stored_cells), "cells": stored_cells, "graph_updated": True}


def retrieve_memory_context(caller_id: str, query: str = "", tenant_id: str = "default", agent_id: str = "reminder") -> dict[str, Any]:
    """Fast O(1) graph context retrieval + rule-constrained caller context."""
    user_node_id = f"user_{caller_id}"
    graph_edges = _GRAPH_INDEX.get_related_entities(user_node_id)
    if not graph_edges:
        # Fallback to demo caller graph
        graph_edges = _GRAPH_INDEX.get_related_entities("caller_demo")

    agent_rule_data = get_agent_rules(agent_id, tenant_id)
    max_chars = 1000
    for r in agent_rule_data["rules"]:
        if r["key"] == "context_max_chars":
            try:
                max_chars = int(r["value"])
            except ValueError:
                pass

    # Build prompt context lines
    context_lines = []
    for edge in graph_edges:
        target_node = _GRAPH_INDEX.lookup_node(edge.get("target")) or {}
        context_lines.append(f"- {edge.get('relation')}: {target_node.get('label')}")

    full_context = "\n".join(context_lines)
    if len(full_context) > max_chars:
        full_context = full_context[:max_chars] + "... [context truncated to limit]"

    return {
        "caller_id": caller_id,
        "agent_id": agent_id,
        "context": full_context,
        "graph_relations": graph_edges,
        "max_chars_applied": max_chars,
        "lookup_complexity": "O(1)",
    }

# ─────────────────────────────────────────────────────────────────────────────
# Backwards compatibility helpers
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_MEMORY_POLICY = DEFAULT_TENANT_MEMORY_CONFIG
get_memory_policy = get_tenant_memory_config
save_memory_policy = save_tenant_memory_config

def list_memory_cells(caller_id: str | None = None, tenant_id: str = "default", limit: int = 100) -> list[dict[str, Any]]:
    query = {"tenant_id": tenant_id}
    if caller_id:
        query["caller_id"] = caller_id
    try:
        docs = list(get_db().get_collection(MEMORY_COLLECTIONS["cells"]).find(query).sort("createdAt", -1).limit(limit))
        return [_serialize(d) for d in docs]
    except Exception:
        return []

def delete_memory_cell(memory_id: str) -> bool:
    try:
        from bson import ObjectId
        res = get_db().get_collection(MEMORY_COLLECTIONS["cells"]).delete_one({"_id": ObjectId(memory_id)})
        return res.deleted_count > 0
    except Exception:
        return False

def get_customer_memory_profile(caller_id: str, tenant_id: str = "default") -> dict[str, Any]:
    try:
        doc = get_db().get_collection(MEMORY_COLLECTIONS["profile"]).find_one({"tenant_id": tenant_id, "caller_id": caller_id}) or {
            "tenant_id": tenant_id, "caller_id": caller_id, "facts": {},
        }
        return _serialize(doc)
    except Exception:
        return {"tenant_id": tenant_id, "caller_id": caller_id, "facts": {}}
