import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from loguru import logger

_db = None


def init_firebase():
    global _db
    if firebase_admin._apps:
        _db = firestore.client()
        return _db

    cred_json = os.environ.get('FIREBASE_CREDENTIALS')
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    elif os.path.exists('firebase-credentials.json'):
        cred = credentials.Certificate('firebase-credentials.json')
    else:
        raise ValueError("Set FIREBASE_CREDENTIALS env var (paste your Firebase service account JSON)")

    firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("Firebase connected")
    return _db


def get_db():
    global _db
    if _db is None:
        return init_firebase()
    return _db


import asyncio
from functools import partial


async def fs_run(func, *args, **kwargs):
    """Run a synchronous Firestore call in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))
