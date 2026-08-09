from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY


def analyze_image(image_bytes: bytes, mime_type: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = "Describe the important visible content in this image in one clear sentence."
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image_part],
            config={"temperature": 0.2},
        )
        description = getattr(response, "text", None) or getattr(response, "output_text", None)
        return description or ""
    except Exception as exc:
        print(f"[vision] error analyzing image: {type(exc).__name__}: {exc}")
        return ""
