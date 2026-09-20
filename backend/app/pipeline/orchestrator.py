import uuid
from time import perf_counter
from typing import Any

from .llm import generate_agent_reply, summarize_conversation
from ..analytics.logger import log_turn
from ..memory.store import get_caller_memory, save_caller_memory
from ..memory.session_store import (
    get_session_history,
    append_session_message,
    set_session_history,
    get_caller_id_from_session,
)
from ..observability import TraceSpan
from .stt import transcribe_audio
from .tts import synthesize_text_to_audio_bytes


def _get_session_history(session_id: str | None = None) -> list[dict[str, str]]:
    if session_id is None:
        return []
    return get_session_history(session_id)


def _get_caller_id_from_session(session_id: str | None = None) -> str | None:
    return get_caller_id_from_session(session_id)


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


def add_image_to_session_history(caller_id: str, description: str) -> None:
    add_file_to_session_history(caller_id, "image", description)


def add_file_to_session_history(caller_id: str, file_type: str, description: str) -> None:
    if not caller_id or not description:
        return
    session_id = f"session-{caller_id}"
    append_session_message(session_id, "user", f"The caller uploaded a {file_type}: {description}")


async def handle_audio_turn(
    audio_bytes: bytes,
    mime: str = "audio/webm",
    session_id: str | None = None,
    tool_event_callback: Any | None = None,
    trace_id: str | None = None,
) -> tuple:
    """Tie STT -> LLM agent -> TTS together with distributed tracing and state persistence."""
    current_trace_id = trace_id or str(uuid.uuid4())
    try:
        # Step 1: STT with OpenTelemetry trace span
        with TraceSpan("stt", "transcribe_audio", trace_id=current_trace_id, metadata={"mime": mime, "audio_bytes": len(audio_bytes)}) as stt_span:
            stt_start = perf_counter()
            transcript = await transcribe_audio(audio_bytes, mime=mime)
            stt_latency_ms = (perf_counter() - stt_start) * 1000

        history = _get_session_history(session_id)
        caller_id = _get_caller_id_from_session(session_id)
        caller_summary = get_caller_memory(caller_id) if caller_id else None

        # Step 2: LLM Reasoning with OpenTelemetry trace span
        used_tools: list[str] = []
        with TraceSpan("llm", "generate_agent_reply", trace_id=current_trace_id, metadata={"caller_id": caller_id}) as llm_span:
            llm_start = perf_counter()
            reply = generate_agent_reply(
                transcript,
                history,
                event_callback=tool_event_callback,
                caller_summary=caller_summary,
                used_tools=used_tools,
            )
            llm_latency_ms = (perf_counter() - llm_start) * 1000

        # Persist conversation turns to distributed session store
        if session_id:
            append_session_message(session_id, "user", transcript)
            append_session_message(session_id, "assistant", reply)

        _save_session_memory(session_id)

        # Step 3: Neural TTS with OpenTelemetry trace span
        with TraceSpan("tts", "synthesize_speech", trace_id=current_trace_id, metadata={"char_count": len(reply)}) as tts_span:
            tts_start = perf_counter()
            tts_audio = await synthesize_text_to_audio_bytes(reply)
            tts_latency_ms = (perf_counter() - tts_start) * 1000

        # Log business telemetry to MongoDB call_logs
        log_turn(
            caller_id=caller_id or "anonymous",
            session_id=session_id or "anonymous",
            transcript=transcript,
            reply_text=reply,
            stt_latency_ms=stt_latency_ms,
            llm_latency_ms=llm_latency_ms,
            tts_latency_ms=tts_latency_ms,
            tool_used=", ".join(dict.fromkeys(used_tools)) if used_tools else "none",
        )

        return transcript, reply, tts_audio
    except Exception as exc:
        print(f"[orchestrator] error processing audio turn: {type(exc).__name__}: {exc}")
        return "", "Sorry, I could not process that audio. Please try again.", b""
