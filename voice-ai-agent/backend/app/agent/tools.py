"""Tools available to the voice agent for Phase 2.

These are intentionally simple mock utilities for now. The LLM can use them to
simulate real agent behavior without requiring a database or external service.
"""

import json


def check_appointment_slots(date: str) -> str:
    """Check mock appointment availability for a clinic visit on a requested date.

    Use this when the caller asks about available appointment times, booking
    availability, or open slots for a specific day. Return realistic placeholder
    time options for the clinic.
    """
    print(f"[tool] check_appointment_slots called with date={date}")
    mock_slots = {
        "2026-08-10": ["09:00 AM", "11:30 AM", "03:15 PM"],
        "2026-08-11": ["10:00 AM", "01:00 PM"],
        "2026-08-12": ["08:30 AM", "02:45 PM", "04:30 PM"],
    }
    slots = mock_slots.get(date, ["09:00 AM", "11:00 AM", "02:00 PM"])
    return json.dumps({"date": date, "available_slots": slots})


def create_lead(name: str, phone: str, reason: str) -> str:
    """Create a mock lead for the clinic when a caller wants to be contacted back.

    Use this when the caller asks to book a callback, leave their details, or
    request follow-up from the clinic. The lead is logged locally for now and
    returned as a confirmation message.
    """
    print(f"[tool] create_lead called with name={name}, phone={phone}, reason={reason}")
    lead_payload = {"name": name, "phone": phone, "reason": reason}
    print(f"[tool] lead payload: {lead_payload}")
    return f"Lead captured for {name}. We will follow up soon."


def get_tool_definitions() -> list[dict]:
    """Return tool definitions in an OpenAI-style function-calling schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": "check_appointment_slots",
                "description": "Use this when a caller asks about available clinic appointment times or open slots for a specific date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "The requested date in YYYY-MM-DD format."}
                    },
                    "required": ["date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_lead",
                "description": "Use this when a caller wants to leave their name, phone number, and reason for follow-up or callback.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The caller's full name."},
                        "phone": {"type": "string", "description": "A phone number to reach the caller."},
                        "reason": {"type": "string", "description": "Why the caller wants a callback or appointment."},
                    },
                    "required": ["name", "phone", "reason"],
                },
            },
        },
    ]
