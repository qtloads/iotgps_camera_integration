"""
MongoDB connection setup.

Single shared MongoClient + database handle, imported by:
 - token_store.py   (persists the IOP GPS login token)
 - log_store.py      (records every /api/live-stream call)

Set config.MONGO_URI to point at your real MongoDB deployment
(e.g. a MongoDB Atlas connection string) before running in production.
"""
from pymongo import MongoClient

import config

_client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
db = _client[config.MONGO_DB_NAME]

tokens_collection = db[config.TOKEN_COLLECTION]
logs_collection = db[config.LOG_COLLECTION]


def _report_mongo_connection():
    """Print MongoDB availability when the application starts."""
    try:
        _client.admin.command("ping")
        print(
            f" * MongoDB connected to database '{config.MONGO_DB_NAME}'.",
            flush=True,
        )
    except Exception as exc:
        # Keep the API available; token/log persistence will retry on use.
        print(f"MongoDB connection failed: {exc}", flush=True)


_report_mongo_connection()
