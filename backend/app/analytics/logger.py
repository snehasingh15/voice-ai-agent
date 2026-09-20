import re
from datetime import datetime, timezone

from groq import Groq

from ..config import GROQ_API_KEY
from ..db.mongo import get_db


def get_sentiment(text: str) -> str:
    if not text:
        return "neutral"
    if not GROQ_API_KEY:
        return "neutral"

    # Fast rule-based sentiment check
    text_lower = text.lower()
    positive_words = {"great", "thank", "thanks", "helpful", "good", "perfect", "awesome", "excellent", "appreciate", "ok", "okay"}
    negative_words = {"bad", "worst", "terrible", "awful", "horrible", "angry", "annoyed", "useless", "cancel", "disappointed", "complaint", "fail"}
    
    words = set(re.findall(r"\w+", text_lower))
    if words & positive_words and not (words & negative_words):
        return "positive"
    if words & negative_words and not (words & positive_words):
        return "negative"

    # LLM classification with graceful fallback
    try:
        client = Groq(api_key=GROQ_API_KEY)
        messages = [
            {
                "role": "system",
                "content": "You are a sentiment classifier. Respond with exactly one word: positive, neutral, or negative.",
            },
            {
                "role": "user",
                "content": f"Classify the sentiment of this message in one word: {text}",
            },
        ]
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.0,
        )
        raw_content = getattr(response.choices[0].message, "content", "") or ""
        normalized = raw_content.strip().lower()
        match = re.search(r"\b(positive|neutral|negative)\b", normalized)
        if match:
            return match.group(1)
    except Exception as exc:
        print(f"[sentiment][info] classifier using heuristic: {exc}")

    return "neutral"


def log_turn(
    caller_id: str,
    session_id: str,
    transcript: str,
    reply_text: str,
    stt_latency_ms: float,
    llm_latency_ms: float,
    tts_latency_ms: float,
    tool_used: str,
) -> None:
    try:
        db = get_db()
        collection = db.get_collection("call_logs")
        sentiment = get_sentiment(transcript)
        document = {
            "timestamp": datetime.now(timezone.utc),
            "caller_id": caller_id,
            "session_id": session_id,
            "transcript": transcript,
            "reply_text": reply_text,
            "stt_latency_ms": float(stt_latency_ms or 0.0),
            "llm_latency_ms": float(llm_latency_ms or 0.0),
            "tts_latency_ms": float(tts_latency_ms or 0.0),
            "tool_used": tool_used or "none",
            "sentiment": sentiment,
        }
        collection.insert_one(document)
    except Exception as e:
        print(f"[logger][warning] Failed to log turn to MongoDB: {e}")
