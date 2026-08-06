import asyncio
import tempfile
from pathlib import Path
import os

import edge_tts


async def synthesize_text_to_audio_bytes(text: str) -> bytes:
    """Use edge-tts to synthesize speech and return bytes (mp3).

    Saves to a temporary file then reads it back into memory.
    """
    if not text:
        return b""

    tmp_dir = tempfile.mkdtemp()
    out_path = Path(tmp_dir) / "tts_output.mp3"

    communicate = edge_tts.Communicate(text, voice="en-US-AriaNeural")
    await communicate.save(str(out_path))

    data = out_path.read_bytes()
    try:
        os.remove(out_path)
        os.rmdir(tmp_dir)
    except Exception:
        pass
    return data
