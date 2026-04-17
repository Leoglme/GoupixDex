"""Wardrobe sync on the local machine: Vinted sign-in (nodriver) then HTTP sync."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import httpx

from config import get_settings
from services.os_service import resolve_vinted_nodriver_user_data_dir
from services.timer_service import TimerService
from services.vinted_chromium_profile_cookie_service import VintedChromiumProfileCookieService
from services.vinted_service import VintedService
from services.vinted_wardrobe import GoupixVintedWardrobeSyncService
from services.vinted_wardrobe.vinted_http_service import VintedHttpService
from services.wardrobe_job_store_service import WardrobeJobStoreService as wardrobe_jobs

logger = logging.getLogger(__name__)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _run_sync_blocking(
    *,
    base_url: str,
    vinted_member_id: int,
    cookie_header: str,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    def _cookie_fn(_u: str) -> tuple[str | None, str]:
        return cookie_header, "nodriver_session"

    sync = GoupixVintedWardrobeSyncService(
        base_url.rstrip("/"),
        vinted_member_id,
        cookie_header_fn=_cookie_fn,
        on_progress=on_progress,
    )
    return sync.run_to_dict()


async def _job_log(job_id: str | None, message: str) -> None:
    logger.info(message)
    if job_id:
        await wardrobe_jobs.append_log_line(job_id, message)


class DesktopWardrobeSyncRunnerService:
    """Orchestrates local wardrobe sync (nodriver + HTTP)."""

    @staticmethod
    async def run_desktop_wardrobe_sync_for_user(
        token: str,
        remote_base: str,
        *,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Open Chrome (nodriver), sign in, read member id and cookies, close the browser,
        then run catalog + sold sync in a thread.
        """
        settings = get_settings()
        hdrs = _headers(token)
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            cred_r = await client.get(f"{remote_base}/users/me/vinted-decrypted", headers=hdrs)
            cred_r.raise_for_status()
            creds: dict[str, Any] = cred_r.json()

        email = creds.get("vinted_email")
        password = creds.get("vinted_password")
        if not email or not password:
            raise RuntimeError("Identifiants Vinted manquants (profil utilisateur).")

        base_url = "https://www.vinted.fr"
        browser_started = False
        member_id: int = 0
        cookie_header = ""
        try:
            await _job_log(job_id, "Démarrage du navigateur Vinted (nodriver)…")
            await VintedService.init_browser()
            browser_started = True
            await VintedService.init_page()
            await TimerService.wait(80)
            await _job_log(job_id, "Connexion / session Vinted…")
            await VintedService.ensure_sign_in(str(email), str(password))
            await _job_log(job_id, "Lecture de l'identifiant membre Vinted…")
            member_id = await VintedService.fetch_logged_in_vinted_user_numeric_id()
            await _job_log(job_id, f"Identifiant membre : {member_id}.")
            cookie_header = await VintedService.export_vinted_session_cookie_header()
            if not cookie_header.strip() and not settings.vinted_browser_ephemeral:
                await _job_log(
                    job_id,
                    "Export CDP ignoré — lecture des cookies depuis le profil Chromium après fermeture…",
                )
        finally:
            if browser_started:
                await _job_log(job_id, "Fermeture du navigateur Vinted…")
                VintedService.close_browser()

        if not cookie_header.strip():
            if settings.vinted_browser_ephemeral:
                raise RuntimeError("Impossible d'exporter les cookies de session Vinted (profil éphémère).")
            profile_dir = resolve_vinted_nodriver_user_data_dir(settings.vinted_user_data_dir)
            cookie_header = VintedChromiumProfileCookieService.read_cookie_header_from_profile(
                profile_dir,
            )
            await _job_log(
                job_id,
                "Cookies lus depuis le fichier profil." if cookie_header.strip() else "Échec lecture cookies disque.",
            )

        if not cookie_header.strip():
            raise RuntimeError("Impossible d'exporter les cookies de session Vinted.")
        if not VintedHttpService.my_orders_session_ok(base_url, cookie_header):
            logger.warning(
                "Session cookie nodriver: my_orders non OK — sold_items peut être vide.",
            )
            await _job_log(job_id, "Avertissement : session « mes commandes » non confirmée (soldes possiblement vides).")

        await _job_log(
            job_id,
            "Démarrage de la synchronisation catalogue + vendus (plusieurs minutes possibles)…",
        )
        loop = asyncio.get_running_loop()

        def on_progress(msg: str) -> None:
            if job_id:
                asyncio.run_coroutine_threadsafe(wardrobe_jobs.append_log_line(job_id, msg), loop)
            logger.info(msg)

        return await asyncio.to_thread(
            _run_sync_blocking,
            base_url=base_url,
            vinted_member_id=member_id,
            cookie_header=cookie_header,
            on_progress=on_progress,
        )
