import json
import asyncio
import urllib.error
import urllib.request

from ..config import DEEPGRAM_API_KEY


async def transcribe_audio(audio_bytes: bytes, mime: str = "audio/webm") -> str:
    """Send recorded audio bytes to Deepgram's listen endpoint and return transcript.

    This implementation sends the full audio after the client signals end-of-utterance.
    For Phase 1 this is acceptable; in Phase 2 we can migrate to realtime websocket
    streaming and endpointing behavior using Deepgram's Realtime API.
    """
    if not DEEPGRAM_API_KEY:
        return ""  # no key; return empty transcript

    url = "https://api.deepgram.com/v1/listen?punctuate=true"

    def do_request():
        req = urllib.request.Request(url, data=audio_bytes, method="POST")
        req.add_header("Authorization", f"Token {DEEPGRAM_API_KEY}")
        req.add_header("Content-Type", mime)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(None, do_request)
        data = json.loads(raw.decode("utf-8"))
        transcript = (
            data.get("results", {})
            .get("channels", [])[0]
            .get("alternatives", [])[0]
            .get("transcript", "")
        )
        return transcript
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        print(f"[stt] Deepgram HTTPError {exc.code}: {exc.reason}; body={body}")
        return ""
    except Exception as exc:
        print(f"[stt] audio transcription failed: {exc}")
        return ""
