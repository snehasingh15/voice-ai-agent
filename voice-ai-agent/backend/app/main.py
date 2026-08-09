"""
Top-level flow (Phase 1 - bare voice loop):

Browser mic -> WebSocket -> backend buffers audio -> Deepgram STT (pre-recorded listen)
-> placeholder reply text -> edge-tts -> backend sends audio bytes back over WebSocket
-> Browser plays audio. Transcript and reply text are also sent as JSON messages
for on-screen display.

This file exposes a single WebSocket endpoint at `/ws/session` which accepts:
- a JSON `start` message specifying `mimeType`,
- binary audio chunk messages (ArrayBuffer blobs), and
- a JSON `stop` message to indicate end-of-utterance.

Phase 2: replace placeholder reply with LLM call and optionally move to true
streaming STT path (Deepgram Realtime).
"""

import json
import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from .pipeline.orchestrator import handle_audio_turn

app = FastAPI()

# Serve a minimal static frontend (optional convenience)
frontend_dir = Path(__file__).resolve().parents[1] / ".." / "frontend"
frontend_dir = frontend_dir.resolve()
app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.websocket("/ws/session")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    audio_buffer = bytearray()
    mime = "audio/webm"
    session_id = f"session-{id(websocket)}"
    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                print(f"WebSocket disconnected cleanly: {msg}")
                break

            # Distinguish between text and binary messages
            if "text" in msg:
                try:
                    data = json.loads(msg["text"]) if msg["text"] else {}
                except Exception:
                    data = {}

                msg_type = data.get("type")
                if msg_type == "start":
                    mime = data.get("mimeType", mime)
                    audio_buffer = bytearray()
                    await websocket.send_json({"type": "status", "message": "recording_started"})
                elif msg_type == "stop":
                    await websocket.send_json({"type": "status", "message": "processing"})
                    # process buffer in background
                    transcript, reply_text, tts_audio = await handle_audio_turn(
                        bytes(audio_buffer),
                        mime=mime,
                        session_id=session_id,
                        tool_event_callback=lambda event: websocket.send_json({"type": "tool_status", "tool": event["tool"], "args": event["args"], "status": event["status"]}),
                    )

                    await websocket.send_json({"type": "transcript", "text": transcript})
                    await websocket.send_json({"type": "reply", "text": reply_text})
                    # send audio bytes back as binary
                    if tts_audio:
                        await websocket.send_bytes(tts_audio)

                    await websocket.send_json({"type": "done"})
                else:
                    # ignore unknown text messages
                    pass
            elif "bytes" in msg:
                audio_buffer.extend(msg["bytes"])
            else:
                # unknown message shape
                pass
    except WebSocketDisconnect:
        print("WebSocket disconnect exception caught")
    except Exception as exc:
        print(f"WebSocket loop error: {exc}")
    finally:
        return
