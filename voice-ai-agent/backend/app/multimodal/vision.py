from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY, GEMINI_TEXT_MODEL


def analyze_image(image_bytes: bytes, mime_type: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = "Describe the important visible content in this image in one clear sentence."
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    model_name = GEMINI_TEXT_MODEL

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, image_part],
            config={"temperature": 0.2},
        )
        description = getattr(response, "text", None) or getattr(response, "output_text", None)
        if description:
            return description
        raise RuntimeError("Image analysis returned no description.")
    except Exception as exc:
        error_message = str(exc)
        print(f"[vision] model {model_name} failed: {type(exc).__name__}: {error_message}")
        raise RuntimeError(f"Failed to analyze image with {model_name}: {error_message}")
