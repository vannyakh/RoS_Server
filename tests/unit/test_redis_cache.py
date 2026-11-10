"""Optional cache behavior without a running Redis server."""

from app.infrastructure.redis import RedisCache


class _Store:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        return True

    async def aclose(self) -> None:
        self.values.clear()


class _Down:
    async def get(self, key: str) -> str | None:
        raise ConnectionError(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        raise ConnectionError(key)

    async def aclose(self) -> None:
        return None


async def test_cache_round_trip_uses_the_injected_client():
    store = _Store()
    cache = RedisCache("redis://unused", client=store)
    assert await cache.set("queue", "1", 30) is True
    assert await cache.get("queue") == "1"
    await cache.close()
    assert store.values == {}


async def test_cache_failure_stays_optional():
    cache = RedisCache("redis://unused", client=_Down())
    assert await cache.get("queue") is None
    assert await cache.set("queue", "1", 30) is False
