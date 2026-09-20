import hashlib
import os
from typing import List

from ..config import GEMINI_API_KEY


def embed_text(text: str) -> List[float]:
    """Return a 768-d embedding for the given text using Gemini or deterministic fallback."""
    if GEMINI_API_KEY:
        try:
            from google import genai

            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.embed_content(
                model="gemini-embedding-001",
                contents=[text],
                config={"output_dimensionality": 768},
            )

            embeddings = getattr(resp, "embeddings", None)
            if embeddings and len(embeddings) > 0:
                first = embeddings[0]
                if hasattr(first, "values"):
                    return list(map(float, first.values))
        except Exception as exc:
            print(f"[embeddings][warning] Gemini embedding call failed ({exc}), using deterministic fallback.")

    # Deterministic fallback vector generation (768-d)
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec = [(float(b) / 255.0) * 2.0 - 1.0 for b in h]
    # Expand to 768 dims
    while len(vec) < 768:
        vec.extend(vec[: min(768 - len(vec), len(vec))])
    return vec[:768]
