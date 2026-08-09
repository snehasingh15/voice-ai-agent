import json
import asyncio
from typing import Any

from groq import Groq

from ..agent.prompts import SYSTEM_PROMPT
from ..agent.tools import check_appointment_slots, create_lead, get_tool_definitions
from ..config import GROQ_API_KEY


def _call_tool_function(tool_name: str, arguments: dict[str, Any], event_callback: Any | None = None) -> str:
    print(f"[tool-call] {tool_name} args={arguments}")
    if event_callback:
        try:
            res = event_callback({"tool": tool_name, "args": arguments, "status": "called"})
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        except Exception as e:
            print(f"[tool-event-callback] scheduling error: {e}")
    if tool_name == "check_appointment_slots":
        return check_appointment_slots(arguments.get("date", ""))
    if tool_name == "create_lead":
        return create_lead(
            arguments.get("name", ""),
            arguments.get("phone", ""),
            arguments.get("reason", ""),
        )
    return f"Tool {tool_name} not implemented"


def _build_messages(
    user_text: str,
    history: list[dict[str, str]],
    tool_definitions: list[dict] | None = None,
    caller_summary: str | None = None,
) -> list[dict[str, Any]]:
    system_prompt = SYSTEM_PROMPT
    if caller_summary:
        system_prompt = (
            f"{SYSTEM_PROMPT} What you remember about this caller: {caller_summary}"
        )

    messages = [{"role": "system", "content": system_prompt}]
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_text})
    return messages


def generate_agent_reply(
    user_text: str,
    history: list[dict[str, str]],
    tool_definitions: list[dict] | None = None,
    client: Any | None = None,
    event_callback: Any | None = None,
    caller_summary: str | None = None,
) -> str:
    """Call Groq with tool use support; execute tools when requested and return final text."""
    if client is None:
        api_key = GROQ_API_KEY
        if not api_key:
            return "I’m not configured to use the LLM yet."
        client = Groq(api_key=api_key)

    if tool_definitions is None:
        tool_definitions = get_tool_definitions()

    messages = _build_messages(user_text, history, tool_definitions, caller_summary=caller_summary)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        tools=tool_definitions,
        temperature=0.2,
    )

    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None) or []

    if not tool_calls:
        return getattr(message, "content", "") or ""

    tool_results: list[dict[str, Any]] = []
    serialized_tool_calls = []
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments or "{}")
        serialized_tool_calls.append(
            {
                "id": getattr(tool_call, "id", "tool-1"),
                "type": "function",
                "function": {"name": function_name, "arguments": tool_call.function.arguments or "{}"},
            }
        )
        tool_output = _call_tool_function(function_name, arguments, event_callback=event_callback)
        tool_results.append({"tool_call_id": getattr(tool_call, "id", "tool-1"), "role": "tool", "content": tool_output})

    follow_up_messages = list(messages)
    follow_up_messages.append({"role": "assistant", "content": "I’m using the requested tool.", "tool_calls": serialized_tool_calls})
    follow_up_messages.extend(tool_results)
    follow_up_response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=follow_up_messages,
        tools=tool_definitions,
        temperature=0.2,
    )
    follow_up_message = follow_up_response.choices[0].message
    return getattr(follow_up_message, "content", "") or ""


def summarize_conversation(history: list[dict[str, str]]) -> str:
    if not history:
        return ""

    conversation_lines = []
    for item in history:
        role = item.get("role", "unknown")
        content = item.get("content", "")
        if role == "user":
            conversation_lines.append(f"Caller: {content}")
        elif role == "assistant":
            conversation_lines.append(f"Assistant: {content}")
        else:
            conversation_lines.append(f"{role.capitalize()}: {content}")

    messages = [
        {
            "role": "system",
            "content": "You are a concise summarization assistant."
        },
        {
            "role": "user",
            "content": (
                "Summarize the key facts about this caller and what they discussed, "
                "in 2-3 sentences, for future reference.\n\n"
                "Conversation:\n"
                + "\n".join(conversation_lines)
            ),
        },
    ]

    api_key = GROQ_API_KEY
    if not api_key:
        return ""
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.2,
    )
    return getattr(response.choices[0].message, "content", "") or ""
