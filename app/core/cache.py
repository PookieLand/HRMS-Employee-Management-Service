import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import redis
from redis import Redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    _instance: Redis | None = None

    @classmethod
    def get_client(cls) -> Redis:
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            logger.info(
                f"Redis client connected to {settings.REDIS_HOST}:{settings.REDIS_PORT}"
            )
        return cls._instance

    @classmethod
    def close(cls):
        if cls._instance:
            cls._instance.close()
            cls._instance = None


def get_cache_key(prefix: str, identifier: str | int) -> str:
    return f"{prefix}:{identifier}"


def json_serializer(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def get_from_cache(key: str) -> Any | None:
    try:
        client = RedisClient.get_client()
        data = client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Cache get error: {e}")
        return None


def set_to_cache(key: str, value: Any, ttl: int = settings.CACHE_TTL) -> bool:
    try:
        client = RedisClient.get_client()
        client.setex(key, ttl, json.dumps(value, default=json_serializer))
        return True
    except Exception as e:
        logger.error(f"Cache set error: {e}")
        return False


def delete_from_cache(key: str) -> bool:
    try:
        client = RedisClient.get_client()
        client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Cache delete error: {e}")
        return False


def clear_cache_pattern(pattern: str) -> bool:
    try:
        client = RedisClient.get_client()
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
        return True
    except Exception as e:
        logger.error(f"Cache clear pattern error: {e}")
        return False
