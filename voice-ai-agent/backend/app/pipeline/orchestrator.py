from typing import Any

from .llm import generate_agent_reply, summarize_conversation
from ..memory.store import get_caller_memory, save_caller_memory
from .stt import transcribe_audio
from .tts import synthesize_text_to_audio_bytes


SESSION_HISTORY: list[dict[str, list[dict[str, str]]]] = []


def _get_session_history(session_id: str | None = None) -> list[dict[str, str]]:
    if session_id is None:
        return []
    for entry in SESSION_HISTORY:
        if entry.get("session_id") == session_id:
            return entry["history"]
    new_entry = {"session_id": session_id, "history": []}
    SESSION_HISTORY.append(new_entry)
    return new_entry["history"]


def _get_caller_id_from_session(session_id: str | None = None) -> str | None:
    if not session_id:
        return None
    if "|" in session_id:
        return session_id.split("|", 1)[1]
    if session_id.startswith("session-"):
        return session_id[len("session-"):]
    return session_id


def _history_has_meaningful_user_content(history: list[dict[str, str]]) -> bool:
    if not history:
        return False
    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
    for item in history:
        if item.get("role") != "user":
            continue
        text = item.get("content", "").strip().lower()
        if not text:
            continue
        if text in greetings:
            continue
        if len(text.split()) >= 3:
            return True
    return False


def _save_session_memory(session_id: str | None = None) -> None:
    caller_id = _get_caller_id_from_session(session_id)
    if not caller_id:
        return
    history = _get_session_history(session_id)
    if not _history_has_meaningful_user_content(history):
        return
    summary = summarize_conversation(history)
    if summary:
        save_caller_memory(caller_id, summary)


def _find_history_by_caller_id(caller_id: str | None = None) -> list[dict[str, str]] | None:
    if not caller_id:
        return None
    for entry in reversed(SESSION_HISTORY):
        session_id = entry.get("session_id")
        if session_id == f"session-{caller_id}" or session_id.endswith(f"|{caller_id}"):
            return entry["history"]
    return None


def add_image_to_session_history(caller_id: str, description: str) -> None:
    if not caller_id or not description:
        return
    history = _find_history_by_caller_id(caller_id)
    if history is None:
        history = _get_session_history(f"session-{caller_id}")
    history.append({"role": "user", "content": f"The caller uploaded an image: {description}"})


async def handle_audio_turn(audio_bytes: bytes, mime: str = "audio/webm", session_id: str | None = None, tool_event_callback: Any | None = None) -> tuple:
    """Tie STT -> LLM agent -> TTS together and return (transcript, reply_text, audio_bytes)."""
    try:
        transcript = await transcribe_audio(audio_bytes, mime=mime)

        history = _get_session_history(session_id)
        caller_id = _get_caller_id_from_session(session_id)
        caller_summary = get_caller_memory(caller_id) if caller_id else None
        reply = generate_agent_reply(
            transcript,
            history,
            event_callback=tool_event_callback,
            caller_summary=caller_summary,
        )

        history.append({"role": "user", "content": transcript})
        history.append({"role": "assistant", "content": reply})

        _save_session_memory(session_id)

        tts_audio = await synthesize_text_to_audio_bytes(reply)

        return transcript, reply, tts_audio
    except Exception as exc:
        print(f"[orchestrator] error processing audio turn: {type(exc).__name__}: {exc}")
        return "", "Sorry, I could not process that audio. Please try again.", b""
