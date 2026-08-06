from dotenv import load_dotenv
import os

load_dotenv()

# Load Deepgram API key from environment; do NOT hardcode keys.
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
