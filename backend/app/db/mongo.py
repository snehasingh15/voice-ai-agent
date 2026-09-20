import certifi
from pymongo import MongoClient
from ..config import MONGODB_URI, MONGODB_DB_NAME

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI is not configured in environment")
        
        # Try standard certifi connection first, with fallback to tlsAllowInvalidCertificates if Windows SSL handshake fails
        try:
            _client = MongoClient(
                MONGODB_URI,
                tls=True,
                tlsCAFile=certifi.where(),
                tlsAllowInvalidCertificates=True,
                serverSelectionTimeoutMS=8000,
                connectTimeoutMS=8000,
            )
            # Trigger quick server selection check
            _client.admin.command('ping')
        except Exception as e:
            print(f"[mongo][warning] Primary TLS check failed: {e}. Retrying with relaxed TLS options...")
            _client = MongoClient(
                MONGODB_URI,
                tlsAllowInvalidCertificates=True,
                serverSelectionTimeoutMS=8000,
                connectTimeoutMS=8000,
            )
            
    return _client


def get_db(name: str = None):
    client = get_client()
    if name:
        return client[name]
    if MONGODB_DB_NAME:
        return client[MONGODB_DB_NAME]
    return client.get_default_database()


def get_knowledge_collection():
    db = get_db()
    return db.get_collection("knowledge_base")
