from typing import Any

from .llm import generate_agent_reply
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


async def handle_audio_turn(audio_bytes: bytes, mime: str = "audio/webm", session_id: str | None = None, tool_event_callback: Any | None = None) -> tuple:
    """Tie STT -> LLM agent -> TTS together and return (transcript, reply_text, audio_bytes)."""
    try:
        transcript = await transcribe_audio(audio_bytes, mime=mime)

        history = _get_session_history(session_id)
        reply = generate_agent_reply(transcript, history, event_callback=tool_event_callback)

        history.append({"role": "user", "content": transcript})
        history.append({"role": "assistant", "content": reply})

        tts_audio = await synthesize_text_to_audio_bytes(reply)

        return transcript, reply, tts_audio
    except Exception as exc:
        print(f"[orchestrator] error processing audio turn: {type(exc).__name__}: {exc}")
        return "", "Sorry, I could not process that audio. Please try again.", b""
