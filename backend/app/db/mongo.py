import certifi
from pymongo import MongoClient
from ..config import MONGODB_URI, MONGODB_DB_NAME

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI is not configured in environment")

        try:
            _client = MongoClient(
                MONGODB_URI,
                tls=True,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=20000,
                connectTimeoutMS=20000,
                socketTimeoutMS=20000,
            )
            _client.admin.command("ping")
        except Exception as exc:
            _client = None
            raise RuntimeError(
                "MongoDB connection failed. Check MONGODB_URI, Atlas Network Access, "
                f"database user credentials, and TLS settings. Original error: {exc}"
            ) from exc

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