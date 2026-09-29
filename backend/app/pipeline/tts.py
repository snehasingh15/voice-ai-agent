import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from collections import OrderedDict
import os

import edge_tts

from ..agent_config import get_configured_tts

_TTS_CACHE: OrderedDict[str, bytes] = OrderedDict()
_TTS_CACHE_MAX_ITEMS = 64


def _tts_cache_key(text: str, voice: str) -> str:
    return f"{voice}::{text.strip()}"


def _get_tts_cache(key: str) -> bytes | None:
    cached = _TTS_CACHE.get(key)
    if cached is not None:
        _TTS_CACHE.move_to_end(key)
    return cached


def _set_tts_cache(key: str, value: bytes) -> None:
    if not value:
        return
    _TTS_CACHE[key] = value
    _TTS_CACHE.move_to_end(key)
    while len(_TTS_CACHE) > _TTS_CACHE_MAX_ITEMS:
        _TTS_CACHE.popitem(last=False)


async def synthesize_text_to_audio_bytes(text: str) -> bytes:
    """Use edge-tts to synthesize speech and return bytes (mp3).

    Saves to a temporary file then reads it back into memory.
    """
    if not text:
        return b""

    configured = get_configured_tts()
    voice = (configured.get("voice") or "en-US-AriaNeural").strip()
    cache_key = _tts_cache_key(text, voice)
    cached = _get_tts_cache(cache_key)
    if cached is not None:
        return cached

    tmp_dir = tempfile.mkdtemp()
    out_path = Path(tmp_dir) / "tts_output.mp3"

    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(str(out_path))

    data = out_path.read_bytes()
    _set_tts_cache(cache_key, data)
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
