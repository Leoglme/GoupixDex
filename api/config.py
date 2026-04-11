"""Application configuration: environment settings and legacy Vinted CLI defaults."""

from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

from pydantic_settings import BaseSettings, SettingsConfigDict

from app_types.vinted import VintedPackageSize


class AppConfig(TypedDict):
    """Global listing defaults for the standalone Vinted CLI (``cli_vinted_listings.py``)."""

    category_path: list[str]
    brand: str
    package_size: VintedPackageSize


config: AppConfig = {
    "category_path": ["Divertissement", "Jeux et puzzles", "Jeux de cartes"],
    "brand": "Pokémon",
    "package_size": "small",
}


class AppSettings(BaseSettings):
    """FastAPI and infrastructure settings (from environment / ``.env``)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "mysql+pymysql://goupix:goupix@127.0.0.1:3306/goupixdex"
    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    upload_dir: str = "uploads"
    usd_to_eur: float = 0.92
    cors_origins: str = "*"
    vinted_publish_stub: bool = True


@lru_cache
def get_settings() -> AppSettings:
    """Cached application settings singleton."""
    return AppSettings()
