from fastapi import APIRouter, Request

from ..db.mongo import get_db
from ..limiter import limiter

router = APIRouter(prefix="/api/analytics")


@router.get("/summary")
@limiter.limit("30/minute")
async def analytics_summary(request: Request):
    db = get_db()
    collection = db.get_collection("call_logs")

    pipeline = [
        {
            "$facet": {
                "summary": [
                    {
                        "$group": {
                            "_id": None,
                            "total_calls": {"$sum": 1},
                            "avg_stt_latency_ms": {"$avg": "$stt_latency_ms"},
                            "avg_llm_latency_ms": {"$avg": "$llm_latency_ms"},
                            "avg_tts_latency_ms": {"$avg": "$tts_latency_ms"},
                        }
                    }
                ],
                "sentiment_counts": [
                    {
                        "$group": {
                            "_id": "$sentiment",
                            "count": {"$sum": 1},
                        }
                    }
                ],
                "tool_counts": [
                    {
                        "$group": {
                            "_id": "$tool_used",
                            "count": {"$sum": 1},
                        }
                    },
                    {"$sort": {"count": -1}},
                    {"$limit": 5},
                ],
            }
        }
    ]

    result = list(collection.aggregate(pipeline))
    if not result:
        return {
            "total_calls": 0,
            "avg_stt_latency_ms": 0,
            "avg_llm_latency_ms": 0,
            "avg_tts_latency_ms": 0,
            "sentiment_breakdown": {"positive": 0, "neutral": 0, "negative": 0},
            "most_used_tools": [],
        }

    summary = result[0].get("summary", [])
    sentiment_counts = result[0].get("sentiment_counts", [])
    tool_counts = result[0].get("tool_counts", [])

    if summary:
        summary_doc = summary[0]
        total_calls = summary_doc.get("total_calls", 0)
        avg_stt_latency_ms = summary_doc.get("avg_stt_latency_ms", 0)
        avg_llm_latency_ms = summary_doc.get("avg_llm_latency_ms", 0)
        avg_tts_latency_ms = summary_doc.get("avg_tts_latency_ms", 0)
    else:
        total_calls = 0
        avg_stt_latency_ms = 0
        avg_llm_latency_ms = 0
        avg_tts_latency_ms = 0

    sentiment_breakdown = {"positive": 0, "neutral": 0, "negative": 0}
    for sentiment in sentiment_counts:
        sentiment_breakdown[sentiment.get("_id", "neutral")] = sentiment.get("count", 0)

    most_used_tools = [
        {"tool": item.get("_id", "unknown"), "count": item.get("count", 0)}
        for item in tool_counts
    ]

    return {
        "total_calls": total_calls,
        "avg_stt_latency_ms": avg_stt_latency_ms,
        "avg_llm_latency_ms": avg_llm_latency_ms,
        "avg_tts_latency_ms": avg_tts_latency_ms,
        "sentiment_breakdown": sentiment_breakdown,
        "most_used_tools": most_used_tools,
    }


@router.get("/recent")
@limiter.limit("30/minute")
async def analytics_recent(request: Request):
    db = get_db()
    collection = db.get_collection("call_logs")
    recent = list(
        collection.find(
            {},
            {
                "_id": 0,
                "caller_id": 1,
                "session_id": 1,
                "transcript": 1,
                "reply_text": 1,
                "stt_latency_ms": 1,
                "llm_latency_ms": 1,
                "tts_latency_ms": 1,
                "tool_used": 1,
                "sentiment": 1,
                "timestamp": 1,
            },
        )
        .sort("timestamp", -1)
        .limit(20)
    )
    return recent



@router.get("/bookings")
@limiter.limit("30/minute")
async def analytics_bookings(request: Request):
    db = get_db()
    collection = db.get_collection("call_logs")
    # Return calls where a tool was used (tool_used != "none")
    bookings = list(
        collection.find(
            {"tool_used": {"$ne": "none"}},
            {"_id": 0, "timestamp": 1, "caller_id": 1, "tool_used": 1, "reply_text": 1, "transcript": 1},
        )
        .sort("timestamp", -1)
        .limit(200)
    )
    return bookings
