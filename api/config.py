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
    #: Base PokéWallet ou URL du proxy (ex. https://goupixdex-proxy.dibodev.fr).
    poke_wallet_base_url: str = "https://api.pokewallet.io"
    #: Si défini, envoi de ``X-Proxy-Secret`` ; la clé API peut rester uniquement sur le proxy.
    poke_wallet_proxy_secret: str | None = None
    poke_wallet_user_agent: str = "GoupixDex/1.0 (+https://goupixdex.dibodev.fr)"
    #: Sur le VPS : ``true`` (navigateur sans fenêtre). En local : laisser ``false`` ou absent.
    vinted_browser_headless: bool = False
    #: Si ``headless`` est ``false`` : fenêtre hors écran (Chrome réel, moins bloqué par Vinted que le vrai headless).
    #: Mettre ``false`` pour retrouver ``--start-maximized`` (ex. Xvfb plein écran).
    vinted_browser_discreet: bool = True
    #: Position initiale (coords écran). Valeurs négatives : souvent hors du moniteur principal (Windows / macOS).
    vinted_browser_discreet_x: int = -2400
    vinted_browser_discreet_y: int = 0
    #: En mode discret, minimise la fenêtre juste après ouverture (peut être désactivé en cas de souci UI).
    vinted_browser_discreet_minimize: bool = True
    #: Chemin explicite vers Chromium/Chrome (ex. ``/usr/bin/chromium`` sur Debian après ``apt install chromium``).
    vinted_chrome_executable: str | None = None


@lru_cache
def get_settings() -> AppSettings:
    """Cached application settings singleton."""
    return AppSettings()
