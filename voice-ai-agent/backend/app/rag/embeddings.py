import os
from typing import List

from ..config import GEMINI_API_KEY


def embed_text(text: str) -> List[float]:
    """Return a 768-d embedding for the given text using Gemini.

    This function tries to use the `google-genai` client if available.
    If no API key or client is available it raises a RuntimeError.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured in environment")

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.embed_content(
            model="gemini-embedding-001",
            contents=[text],
            config={"output_dimensionality": 768},
        )

        embeddings = getattr(resp, "embeddings", None)
        if not embeddings:
            raise RuntimeError("google-genai returned no embeddings")

        first = embeddings[0]
        if hasattr(first, "values"):
            return list(map(float, first.values))

        raise RuntimeError("google-genai embedding response has no values field")
    except Exception as exc:
        raise RuntimeError(
            f"Embedding call failed with google-genai SDK: {exc}"
        ) from exc
