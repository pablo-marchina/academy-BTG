from __future__ import annotations
import json
import logging
from typing import Optional, Any
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis as r
            _redis_client = r.Redis.from_url("redis://localhost:6379/0", decode_responses=True, socket_timeout=2)
            _redis_client.ping()
            logger.info("[Cache] Redis conectado")
        except Exception:
            logger.info("[Cache] Redis indisponivel, usando cache em memoria")
            _redis_client = {}
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    client = _get_redis()
    try:
        if isinstance(client, dict):
            return client.get(key)
        data = client.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 300):
    client = _get_redis()
    try:
        if isinstance(client, dict):
            client[key] = value
            return
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete(key: str):
    client = _get_redis()
    try:
        if isinstance(client, dict):
            client.pop(key, None)
            return
        client.delete(key)
    except Exception:
        pass


def cache_clear_pattern(pattern: str):
    client = _get_redis()
    try:
        if isinstance(client, dict):
            client.clear()
            return
        for key in client.scan_iter(match=pattern):
            client.delete(key)
    except Exception:
        pass
