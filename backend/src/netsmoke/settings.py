from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NETSMOKE_", env_file=".env", extra="ignore")

    app_name: str = "netsmoke"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    config_path: Path = Field(default=Path("/app/config/netsmoke.yaml"))
    database_url: str = "sqlite+aiosqlite:////app/data/netsmoke.db"
    collector_enabled: bool = True


settings = AppSettings()
