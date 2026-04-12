"""Application configuration: environment settings and legacy Vinted CLI defaults."""

from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_types.vinted import VintedPackageSize


class AppConfig(TypedDict):
    """Global listing defaults for the standalone Vinted CLI (``cli_vinted_listings.py``)."""

    category_path: list[str]
    brand: str
    package_size: VintedPackageSize


config: AppConfig = {
    "category_path": [
        "Loisirs et collections",
        "Cartes à collectionner",
        "Cartes à collectionner à l'unité",
    ],
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
    supabase_url: str | None = None
    supabase_api_key: str | None = None
    supabase_storage_bucket: str | None = None
    usd_to_eur: float = 0.92
    cors_origins: str = "*"
    #: Marge initiale (table ``settings``) à la création d’un compte et pour le margin_seeder.
    seed_margin_percent: int = Field(default=60, ge=0, le=500)


@lru_cache
def get_settings() -> AppSettings:
    """Cached application settings singleton."""
    return AppSettings()
