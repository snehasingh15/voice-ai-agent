import json
import re
import asyncio
from typing import Any

from groq import Groq

from ..agent.prompts import SYSTEM_PROMPT, get_active_prompt
from ..agent.tools import (
    check_appointment_slots,
    create_booking,
    initiate_outbound_call,
    list_doctors,
    retrieve_hospital_knowledge,
    update_booking,
    get_tool_definitions,
)
from ..config import GROQ_API_KEY, GEMINI_API_KEY, GROQ_MODELS as CONFIGURED_GROQ_MODELS, GEMINI_TEXT_MODELS


TOOL_PLACEHOLDER_PATTERN = re.compile(r"<function=(?P<name>[^>]+)>(?P<body>.*?)</function>", re.DOTALL)

GROQ_MODELS = [
    model.strip()
    for model in (CONFIGURED_GROQ_MODELS or "").split(",")
    if model.strip()
]

if not GROQ_MODELS:
    GROQ_MODELS = ["openai/gpt-oss-20b"]


def _call_groq_with_fallback(client: Groq, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, temperature: float = 0.2):
    """Try Groq models in fallback order until one succeeds."""
    last_err = None
    for model_name in GROQ_MODELS:
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            err_str = str(exc)
            if "model_not_found" in err_str or "404" in err_str or "does not exist" in err_str:
                last_err = exc
                continue
            # For other non-404 errors, also try smaller/alternative model
            last_err = exc
            print(f"[llm][fallback] Model {model_name} failed: {exc}, trying next model...")
            continue
    raise last_err or RuntimeError("All Groq models failed.")


def _call_gemini_fallback(messages: list[dict[str, Any]]) -> str:
    """Fallback LLM generation using Google Gemini if Groq is unavailable."""
    if not GEMINI_API_KEY:
        return "I am experiencing high demand. Please try again shortly."
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        sys_prompt = next((m["content"] for m in messages if m.get("role") == "system"), SYSTEM_PROMPT)
        chat_contents = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages if m.get("role") != "system"]
        prompt_text = f"System Instructions: {sys_prompt}\n\nConversation:\n" + "\n".join(chat_contents)
        
        fallback_models = [
            model.replace("models/", "").strip()
            for model in (GEMINI_TEXT_MODELS or "").split(",")
            if model.strip()
        ] or ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]
        for m_name in fallback_models:
            try:
                resp = client.models.generate_content(model=m_name, contents=prompt_text, config={"automatic_function_calling": {"disable": True}})
                if resp and resp.text:
                    return resp.text
            except Exception:
                continue
    except Exception as exc:
        print(f"[llm][gemini-fallback] failed: {exc}")
    return "I am here to help. Please share your request or preferred time."


def _call_tool_function(
    tool_name: str,
    arguments: dict[str, Any],
    event_callback: Any | None = None,
    used_tools: list[str] | None = None,
) -> str:
    print(f"[tool-call] {tool_name} args={arguments}")
    if used_tools is not None:
        used_tools.append(tool_name)
    if event_callback:
        try:
            res = event_callback({"tool": tool_name, "args": arguments, "status": "called"})
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        except Exception as e:
            print(f"[tool-event-callback] scheduling error: {e}")
    if tool_name == "list_doctors":
        department = arguments.get("department")
        return list_doctors(department=department)
    if tool_name == "retrieve_hospital_knowledge":
        query = arguments.get("query", "")
        return retrieve_hospital_knowledge(query=query)
    if tool_name == "check_appointment_slots":
        doctor_name = arguments.get("doctor_name", "")
        date = arguments.get("date", "")
        return check_appointment_slots(doctor_name=doctor_name, date=date)
    if tool_name == "create_booking":
        return create_booking(
            patient_name=arguments.get("patient_name", ""),
            doctor_name=arguments.get("doctor_name", ""),
            appointment_date=arguments.get("appointment_date", ""),
            appointment_time=arguments.get("appointment_time", ""),
            caller_id=arguments.get("caller_id"),
            department=arguments.get("department"),
            notes=arguments.get("notes"),
        )
    if tool_name == "update_booking":
        return update_booking(
            booking_id=arguments.get("booking_id", ""),
            action=arguments.get("action", "confirm"),
            new_date=arguments.get("new_date"),
            new_time=arguments.get("new_time"),
            caller_id=arguments.get("caller_id"),
        )
    if tool_name == "initiate_outbound_call":
        return initiate_outbound_call(
            phone_number=arguments.get("phone_number", ""),
            caller_id=arguments.get("caller_id"),
        )
    return json.dumps({"error": f"unknown tool: {tool_name}"})


def _parse_raw_tool_call_from_text(text: str) -> tuple[str, dict[str, Any]] | None:
    match = TOOL_PLACEHOLDER_PATTERN.search(text)
    if not match:
        return None

    tool_name = match.group("name").strip()
    raw_body = match.group("body").strip()
    if not raw_body:
        return tool_name, {}

    try:
        return tool_name, json.loads(raw_body)
    except json.JSONDecodeError as exc:
        print(f"[llm][warning] could not parse raw tool arguments for {tool_name}: {exc}")
        return None


def _build_messages(
    user_text: str,
    history: list[dict[str, str]],
    tool_definitions: list[dict[str, Any]] | None = None,
    caller_summary: str | None = None,
    custom_system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    active_prompt = custom_system_prompt or get_active_prompt()
    system_prompt = active_prompt
    if caller_summary:
        system_prompt = (
            f"{active_prompt} What you remember about this caller: {caller_summary}"
        )
    uploaded_context = [
        item.get("content", "")
        for item in history
        if "I analyzed the uploaded" in item.get("content", "")
    ]
    if uploaded_context:
        system_prompt += (
            " Recent uploaded file context is available below. "
            "When the caller asks about an uploaded image or file, answer directly from this context. "
            "Do not say you cannot view the image. Do not ask where it is stored. "
            "Do not create or mention a support ticket for image-description questions unless the caller explicitly asks for support. "
            "Uploaded file context: " + " | ".join(uploaded_context[-3:])
        )
    system_prompt += (
        " When a tool is needed, do not embed raw function syntax in the reply. "
        "Instead, use the model's tool-calling interface so tool calls are handled by the API."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_text})
    return messages


def generate_agent_reply(
    user_text: str,
    history: list[dict[str, str]],
    tool_definitions: list[dict[str, Any]] | None = None,
    client: Any | None = None,
    event_callback: Any | None = None,
    caller_summary: str | None = None,
    used_tools: list[str] | None = None,
) -> str:
    """Call Groq with model fallback and tool calling support; fallback to Gemini if needed."""
    if client is None:
        api_key = GROQ_API_KEY
        if not api_key:
            messages = _build_messages(user_text, history, tool_definitions, caller_summary=caller_summary)
            return _call_gemini_fallback(messages)
        client = Groq(api_key=api_key)

    if tool_definitions is None:
        tool_definitions = get_tool_definitions()

    messages = _build_messages(user_text, history, tool_definitions, caller_summary=caller_summary)

    try:
        response = _call_groq_with_fallback(client, messages, tools=tool_definitions, temperature=0.2)
    except Exception as exc:
        print(f"[llm][warning] Groq failed ({exc}), attempting Gemini fallback...")
        return _call_gemini_fallback(messages)

    message = response.choices[0].message
    reply_text = getattr(message, "content", "") or ""
    tool_calls = getattr(message, "tool_calls", None) or []

    if not tool_calls and "<function=" in reply_text:
        print(f"[llm][warning] reply contains raw tool placeholder text: {reply_text}")
        parsed = _parse_raw_tool_call_from_text(reply_text)
        if parsed:
            function_name, arguments = parsed
            tool_output = _call_tool_function(function_name, arguments, event_callback=event_callback, used_tools=used_tools)
            follow_up_messages = list(messages)
            follow_up_messages.append({
                "role": "assistant",
                "content": "IÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢m using the requested tool.",
                "tool_calls": [
                    {
                        "id": "tool-1",
                        "type": "function",
                        "function": {"name": function_name, "arguments": json.dumps(arguments)},
                    }
                ],
            })
            follow_up_messages.append({"role": "tool", "content": tool_output})
            try:
                follow_up_response = _call_groq_with_fallback(client, follow_up_messages, tools=tool_definitions, temperature=0.2)
                follow_up_message = follow_up_response.choices[0].message
                final_reply = getattr(follow_up_message, "content", "") or ""
                if "<function=" in final_reply:
                    return final_reply.replace("<function=", "[tool-call]")
                return final_reply
            except Exception:
                return "The requested information has been updated."

    if tool_calls:
        tool_results: list[dict[str, Any]] = []
        serialized_tool_calls = []
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except Exception:
                arguments = {}
            serialized_tool_calls.append(
                {
                    "id": getattr(tool_call, "id", "tool-1"),
                    "type": "function",
                    "function": {"name": function_name, "arguments": tool_call.function.arguments or "{}"},
                }
            )
            tool_output = _call_tool_function(function_name, arguments, event_callback=event_callback, used_tools=used_tools)
            tool_results.append({"tool_call_id": getattr(tool_call, "id", "tool-1"), "role": "tool", "content": tool_output})

        follow_up_messages = list(messages)
        follow_up_messages.append({"role": "assistant", "content": "IÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢m using the requested tool.", "tool_calls": serialized_tool_calls})
        follow_up_messages.extend(tool_results)
        try:
            follow_up_response = _call_groq_with_fallback(client, follow_up_messages, tools=tool_definitions, temperature=0.2)
            follow_up_message = follow_up_response.choices[0].message
            final_reply = getattr(follow_up_message, "content", "") or ""
            if "<function=" in final_reply:
                return final_reply.replace("<function=", "[tool-call]")
            return final_reply
        except Exception:
            return "I have processed your request."

    return reply_text


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
        return _call_gemini_fallback(messages)
    try:
        client = Groq(api_key=api_key)
        response = _call_groq_with_fallback(client, messages, temperature=0.2)
        return getattr(response.choices[0].message, "content", "") or ""
    except Exception:
        return _call_gemini_fallback(messages)
