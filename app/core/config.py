"""Application settings loaded from the environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RoS Private Server"
    app_env: str = "development"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./ros_server.db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    redis_url: str = "redis://localhost:6379/0"
    game_tick_rate: int = 20
    max_players_per_match: int = 100
    bot_fill: int = 7
    queue_wait_seconds: float = 2.0
    map_publishers: str = ""
    map_storage_dir: str = ""
    admin_username: str = ""
    admin_password: str = ""
    # Shared key for the original-client gateway (bigworld_gateway/). Empty disables /api/v1/gateway.
    gateway_api_key: str = ""
    # Diamonds (original-client "yuanbao") a new gateway player starts with.
    gateway_starting_yuanbao: int = 100000
    # Season the original client is in; its Stats page "Season" tab reads this season's records.
    gateway_current_season: int = 1

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
