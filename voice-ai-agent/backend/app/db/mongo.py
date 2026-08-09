import certifi
from pymongo import MongoClient
from ..config import MONGODB_URI, MONGODB_DB_NAME


_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI is not configured in environment")
        _client = MongoClient(
            MONGODB_URI,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=10000,
        )
    return _client


def get_db(name: str = None):
    client = get_client()
    if name:
        return client[name]
    if MONGODB_DB_NAME:
        return client[MONGODB_DB_NAME]
    # default database from connection string
    return client.get_default_database()


def get_knowledge_collection():
    db = get_db()
    return db.get_collection("knowledge_base")
