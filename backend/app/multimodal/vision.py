from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY, GEMINI_TEXT_MODEL, GEMINI_TEXT_MODELS


def _configured_models() -> list[str]:
    configured = [GEMINI_TEXT_MODEL]
    configured.extend(model.strip() for model in (GEMINI_TEXT_MODELS or "").split(","))
    models = []
    seen = set()
    for model in configured:
        model_name = model.replace("models/", "").strip() if model else ""
        if model_name and model_name not in seen:
            seen.add(model_name)
            models.append(model_name)
    return models

def analyze_image(image_bytes: bytes, mime_type: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = "Describe the important visible content in this medical/diagnostic image in one clear sentence."
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    
    models_to_try = _configured_models()
    seen = set()
    last_error = None

    for model_name in models_to_try:
        if not model_name or model_name in seen:
            continue
        seen.add(model_name)
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, image_part],
                config={"temperature": 0.2, "automatic_function_calling": {"disable": True}},
            )
            description = getattr(response, "text", None) or getattr(response, "output_text", None)
            if description and description.strip():
                return description.strip()
        except Exception as exc:
            last_error = exc
            print(f"[vision] model {model_name} failed: {type(exc).__name__}: {exc}")

    raise RuntimeError(f"Failed to analyze image with available Gemini models: {last_error}")
