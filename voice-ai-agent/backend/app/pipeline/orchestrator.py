from .stt import transcribe_audio
from .tts import synthesize_text_to_audio_bytes


async def handle_audio_turn(audio_bytes: bytes, mime: str = "audio/webm") -> tuple:
    """Tie STT -> placeholder reply -> TTS together and return (transcript, reply_text, audio_bytes).

    NOTE: The reply is a fixed placeholder string for Phase 1. Replace this with
    an LLM call in Phase 2.
    """
    transcript = await transcribe_audio(audio_bytes, mime=mime)

    # Placeholder reply — Phase 1 only
    reply = f"I heard you say: {transcript}. This is a test response."

    tts_audio = await synthesize_text_to_audio_bytes(reply)

    return transcript, reply, tts_audio
