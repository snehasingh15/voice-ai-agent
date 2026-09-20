from dotenv import load_dotenv
import os

load_dotenv()

# Load API keys from environment; do NOT hardcode secrets.
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Gemini (Google) embeddings API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Gemini text/multimodal model for image understanding
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.7-flash")
GEMINI_TEXT_MODELS = os.getenv(
    "GEMINI_TEXT_MODELS",
    "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-flash-latest,gemini-2.5-flash,gemini-3.8-flash",
)
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_MODELS = os.getenv(
    "GROQ_MODELS",
    "openai/gpt-oss-20b,qwen/qwen3.8-27b,qwen/qwen3.6-27b,openai/gpt-oss-120b,groq/compound-mini",
)
# MongoDB connection URI (Atlas)
MONGODB_URI = os.getenv("MONGODB_URI")
# MongoDB database name if not included in the URI
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")
# Simple admin password for the frontend password gate (or fallback for JWT authentication)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Redis / KeyDB connection URL for distributed session storage (optional, falls back to MongoDB TTL collection)
REDIS_URL = os.getenv("REDIS_URL")

# JWT authentication configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "voice-ai-production-super-secret-jwt-key-change-in-env")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))

# Select outbound telephony provider: exotel or twilio.
TELEPHONY_PROVIDER = os.getenv("TELEPHONY_PROVIDER", "exotel").lower()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

# Exotel outbound/inbound telephony integration. Keep these in .env only.
EXOTEL_ACCOUNT_SID = os.getenv("EXOTEL_ACCOUNT_SID")
EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN")
EXOTEL_CALLER_ID = os.getenv("EXOTEL_CALLER_ID")
EXOTEL_APP_URL = os.getenv("EXOTEL_APP_URL")
EXOTEL_STREAM_URL = os.getenv("EXOTEL_STREAM_URL")
EXOTEL_FLOW_URL = os.getenv("EXOTEL_FLOW_URL")
EXOTEL_STATUS_CALLBACK_URL = os.getenv("EXOTEL_STATUS_CALLBACK_URL")
EXOTEL_API_BASE_URL = os.getenv("EXOTEL_API_BASE_URL", "https://api.in.exotel.com")

# Twilio outbound/live media-stream integration. Keep these in .env only.
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_VOICE_URL = os.getenv("TWILIO_VOICE_URL")
TWILIO_STREAM_URL = os.getenv("TWILIO_STREAM_URL")
TWILIO_STATUS_CALLBACK_URL = os.getenv("TWILIO_STATUS_CALLBACK_URL")
