"""eBay OAuth 2.0 (authorization code + refresh) for user tokens."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from config import AppSettings, get_settings

logger = logging.getLogger(__name__)

EBAY_SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
]


class EbayOAuthError(RuntimeError):
    """Erreur OAuth eBay exploitable côté UI (code + message lisibles)."""

    def __init__(self, code: str, message: str, *, status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status = status

    def __str__(self) -> str:
        return self.message or self.code


def _describe_ebay_oauth_error(status: int, body: str) -> EbayOAuthError:
    """Transforme un body 4xx eBay (`{"error": "...", "error_description": "..."}`)
    en exception `RuntimeError` lisible, avec un code applicatif stable pour l'UI."""
    payload: dict[str, Any] = {}
    try:
        parsed = json.loads(body) if body else {}
        if isinstance(parsed, dict):
            payload = parsed
    except ValueError:
        payload = {}
    err = str(payload.get("error") or "").strip()
    desc = str(payload.get("error_description") or "").strip()

    if err == "invalid_scope":
        return EbayOAuthError(
            "ebay_scope_mismatch",
            "Votre consentement eBay n'inclut pas tous les scopes demandés. "
            "Reconnectez votre compte eBay dans les Paramètres pour accorder les nouveaux accès.",
            status=status,
        )
    if err in {"invalid_grant", "invalid_token"}:
        return EbayOAuthError(
            "ebay_refresh_token_invalid",
            "Le refresh token eBay a expiré ou a été révoqué. Reconnectez votre compte eBay.",
            status=status,
        )
    if err == "invalid_client":
        return EbayOAuthError(
            "ebay_client_invalid",
            "Identifiants application eBay invalides (client_id / client_secret). "
            "Vérifiez la configuration serveur.",
            status=status,
        )

    message = desc or err or f"Erreur eBay ({status})."
    return EbayOAuthError(err or "ebay_token_http_error", message, status=status)


def _auth_base_url(app: AppSettings) -> str:
    return "https://auth.sandbox.ebay.com" if app.ebay_use_sandbox else "https://auth.ebay.com"


def _api_base_url(app: AppSettings) -> str:
    return "https://api.sandbox.ebay.com" if app.ebay_use_sandbox else "https://api.ebay.com"


def ebay_oauth_configured(app: AppSettings | None = None) -> bool:
    s = app or get_settings()
    return bool(
        (s.ebay_client_id or "").strip()
        and (s.ebay_client_secret or "").strip()
        and (s.ebay_redirect_uri or "").strip(),
    )


def build_authorization_url(*, state: str, app: AppSettings | None = None) -> str:
    """Consent page URL (GET in browser)."""
    s = app or get_settings()
    if not ebay_oauth_configured(s):
        raise RuntimeError("ebay_oauth_not_configured")
    q = urlencode(
        {
            "client_id": s.ebay_client_id.strip(),
            "redirect_uri": s.ebay_redirect_uri.strip(),
            "response_type": "code",
            "scope": " ".join(EBAY_SCOPES),
            "state": state,
        },
    )
    return f"{_auth_base_url(s)}/oauth2/authorize?{q}"


def _basic_auth_header(app: AppSettings) -> str:
    raw = f"{app.ebay_client_id.strip()}:{app.ebay_client_secret.strip()}"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


async def exchange_authorization_code(code: str, *, app: AppSettings | None = None) -> dict[str, Any]:
    """Trade one-time ``code`` for access + refresh tokens."""
    s = app or get_settings()
    if not ebay_oauth_configured(s):
        raise RuntimeError("ebay_oauth_not_configured")
    url = f"{_api_base_url(s)}/identity/v1/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "code": code.strip(),
        "redirect_uri": s.ebay_redirect_uri.strip(),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {_basic_auth_header(s)}",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, data=data, headers=headers)
    if resp.status_code >= 400:
        logger.warning("eBay token exchange failed: %s %s", resp.status_code, resp.text[:500])
        raise _describe_ebay_oauth_error(resp.status_code, resp.text)
    return resp.json()


async def refresh_user_access_token(refresh_token: str, *, app: AppSettings | None = None) -> dict[str, Any]:
    """Rafraîchit l'access token utilisateur.

    On ne force **volontairement pas** le paramètre ``scope`` : eBay renvoie alors
    un token portant les scopes tels qu'ils ont été consentis au moment de la
    connexion. C'est indispensable quand ``EBAY_SCOPES`` évolue (ajout de
    ``sell.fulfillment`` par exemple) : les utilisateurs déjà connectés avant
    l'ajout continuent de publier (inventory + account) sans reconsentement ;
    les fonctionnalités nécessitant le nouveau scope détecteront son absence et
    proposeront la reconnexion.
    """
    s = app or get_settings()
    if not ebay_oauth_configured(s):
        raise RuntimeError("ebay_oauth_not_configured")
    url = f"{_api_base_url(s)}/identity/v1/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token.strip(),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {_basic_auth_header(s)}",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, data=data, headers=headers)
    if resp.status_code >= 400:
        logger.warning("eBay refresh failed: %s %s", resp.status_code, resp.text[:500])
        raise _describe_ebay_oauth_error(resp.status_code, resp.text)
    return resp.json()
