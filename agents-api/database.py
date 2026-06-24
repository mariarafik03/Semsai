import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

_client = None
_db = None

def get_db():
    """Return (and lazily create) the shared synchronous MongoDB client."""
    global _client, _db
    if _db is not None:
        return _db

    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("MONGO_URI not set in environment variables.")

    _client = MongoClient(
        uri,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=60000,
    )
    _db = _client.get_default_database()
    return _db
