"""Optional Redis cache. Importing this module does not open a connection."""

from redis.asyncio import Redis

from app.core.config import settings


class RedisCache:
    def __init__(self, url: str, client: Redis | None = None) -> None:
        self.url = url
        self._client = client

    def _connect(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(self.url, decode_responses=True, socket_connect_timeout=0.2)
        return self._client

    async def get(self, key: str) -> str | None:
        try:
            return await self._connect().get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> bool:
        try:
            await self._connect().set(key, value, ex=ttl_seconds)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        await client.aclose()


_cache = RedisCache(settings.redis_url)


def get_cache() -> RedisCache:
    return _cache
