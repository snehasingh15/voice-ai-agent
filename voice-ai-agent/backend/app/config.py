from dotenv import load_dotenv
import os

load_dotenv()

# Load API keys from environment; do NOT hardcode secrets.
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Gemini (Google) embeddings API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# MongoDB connection URI (Atlas)
MONGODB_URI = os.getenv("MONGODB_URI")
# MongoDB database name if not included in the URI
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")
