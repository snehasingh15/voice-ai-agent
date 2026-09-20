import asyncio
import shutil
import subprocess
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


async def _convert_mp3_with_ffmpeg(mp3_bytes: bytes, output_format: str, codec: str, sample_rate: str = "8000") -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[tts] ffmpeg not found; install ffmpeg for telephony audio playback")
        return b""

    tmp_dir = tempfile.mkdtemp()
    input_path = Path(tmp_dir) / "tts_input.mp3"
    output_path = Path(tmp_dir) / "tts_output.audio"
    input_path.write_bytes(mp3_bytes)

    try:
        proc = await asyncio.create_subprocess_exec(
            ffmpeg,
            "-y",
            "-i",
            str(input_path),
            "-f",
            output_format,
            "-acodec",
            codec,
            "-ac",
            "1",
            "-ar",
            sample_rate,
            str(output_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode != 0 or not output_path.exists():
            print(f"[tts] ffmpeg conversion failed with code {proc.returncode}")
            return b""
        return output_path.read_bytes()
    finally:
        try:
            os.remove(input_path)
            if output_path.exists():
                os.remove(output_path)
            os.rmdir(tmp_dir)
        except Exception:
            pass


async def synthesize_text_to_pcm16_8k(text: str) -> bytes:
    """Synthesize speech and convert it to Exotel raw PCM 16-bit 8k mono.

    Exotel Voicebot expects raw/slin PCM little-endian, base64 encoded over
    WebSocket. Edge TTS gives us MP3, so ffmpeg must be installed locally.
    """
    mp3_bytes = await synthesize_text_to_audio_bytes(text)
    if not mp3_bytes:
        return b""

    return await _convert_mp3_with_ffmpeg(mp3_bytes, output_format="s16le", codec="pcm_s16le")


async def synthesize_text_to_mulaw_8k(text: str) -> bytes:
    """Synthesize speech and convert it to Twilio Media Streams μ-law 8k mono."""
    mp3_bytes = await synthesize_text_to_audio_bytes(text)
    if not mp3_bytes:
        return b""
    return await _convert_mp3_with_ffmpeg(mp3_bytes, output_format="mulaw", codec="pcm_mulaw")
