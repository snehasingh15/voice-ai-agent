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
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .multimodal.vision import analyze_image
from .pipeline.orchestrator import add_image_to_session_history, handle_audio_turn, _save_session_memory

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Serve a minimal static frontend (optional convenience)
frontend_dir = Path(__file__).resolve().parents[1] / ".." / "frontend"
frontend_dir = frontend_dir.resolve()
app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.websocket("/ws/session")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    audio_buffer = bytearray()
    mime = "audio/webm"
    caller_id = None
    session_id = None
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
                if msg_type == "session_start":
                    caller_id = data.get("caller_id", "anonymous") or "anonymous"
                    session_id = f"session-{caller_id}"
                    await websocket.send_json({"type": "status", "message": "session_started"})
                elif msg_type == "start":
                    if session_id is None:
                        caller_id = caller_id or "anonymous"
                        session_id = f"session-{caller_id}"
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
        if session_id is not None:
            _save_session_memory(session_id)
        return


@app.post("/api/upload-image")
async def upload_image(caller_id: str = Form(...), image: UploadFile = File(...)):
    if not caller_id:
        raise HTTPException(status_code=400, detail="caller_id is required")
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="A valid image file is required")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    try:
        description = analyze_image(image_bytes, image.content_type)
    except Exception as exc:
        print(f"[vision] analyze_image failed: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {exc}")

    add_image_to_session_history(caller_id, description)
    return {"description": description}
