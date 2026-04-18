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


#: Default eBay France (EBAY_FR) leaf category for single JCC / Pokémon cards (Inventory API).
#: Adjust if eBay taxonomy changes; validate via Taxonomy API for ``EBAY_FR``.
EBAY_FR_DEFAULT_LEAF_CATEGORY_ID = "183454"


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
    #: Initial margin (``settings`` table) when creating an account and for ``margin_seeder``.
    seed_margin_percent: int = Field(default=60, ge=0, le=500)
    #: PokéWallet base URL or proxy URL (e.g. https://goupixdex-proxy.dibodev.fr).
    poke_wallet_base_url: str = "https://api.pokewallet.io"
    #: When set, sends ``X-Proxy-Secret``; the API key can stay only on the proxy.
    poke_wallet_proxy_secret: str | None = None
    poke_wallet_user_agent: str = "GoupixDex/1.0 (+https://goupixdex.dibodev.fr)"
    #: On the VPS: ``true`` (headless browser). Locally: leave ``false`` or unset.
    vinted_browser_headless: bool = False
    #: When ``headless`` is ``false``: off-screen window (real Chrome; often less blocked by Vinted than true headless).
    #: Set ``false`` to use ``--start-maximized`` (e.g. full-screen Xvfb).
    vinted_browser_discreet: bool = True
    #: Initial window position (screen coords). Negative values: often off the primary monitor (Windows / macOS).
    vinted_browser_discreet_x: int = -2400
    vinted_browser_discreet_y: int = 0
    #: In discreet mode, minimize the window right after open (can be disabled if UI glitches).
    vinted_browser_discreet_minimize: bool = True
    #: Explicit path to Chromium/Chrome (e.g. ``/usr/bin/chromium`` on Debian after ``apt install chromium``).
    vinted_chrome_executable: str | None = None
    #: Persistent nodriver Chrome profile (Vinted session). Empty = default folder under user local data.
    vinted_user_data_dir: str | None = None
    #: When ``true``: no ``user_data_dir`` (throwaway profile each launch, as before).
    vinted_browser_ephemeral: bool = False
    #: eBay REST (Inventory API + OAuth). Leave unset to disable server-side eBay features.
    ebay_client_id: str | None = None
    ebay_client_secret: str | None = None
    #: RuName / redirect URI registered in eBay Developer → Your eBay Sign-in Settings.
    ebay_redirect_uri: str | None = None
    #: Use sandbox API hosts (``auth.sandbox.ebay.com``, ``api.sandbox.ebay.com``).
    ebay_use_sandbox: bool = True


@lru_cache
def get_settings() -> AppSettings:
    """Cached application settings singleton."""
    return AppSettings()
