"""Read Vinted cookies from the Chromium profile directory (after the browser closes)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class VintedChromiumProfileCookieService:
    """Vinted session cookies from the Chromium profile SQLite store (non-CDP)."""

    @staticmethod
    def read_cookie_header_from_profile(profile_dir: Path) -> str:
        """
        Build a ``Cookie`` header from ``Default/Network/Cookies`` (or ``Default/Cookies``).

        Used when CDP ``Storage.getCookies`` calls stall (nodriver / heavy page): after Chrome exits,
        the SQLite file is readable and ``browser_cookie3`` decrypts values (Windows DPAPI).

        Args:
            profile_dir: Profile root (e.g. ``.../vinted-nodriver-profile``).

        Returns:
            ``name=value; …`` string for domains containing ``vinted``, or empty.
        """
        profile_dir = profile_dir.resolve()
        network = profile_dir / "Default" / "Network" / "Cookies"
        legacy = profile_dir / "Default" / "Cookies"
        cookie_db = network if network.is_file() else legacy
        if not cookie_db.is_file():
            logger.warning("Chromium Cookies file not found under %s", profile_dir)
            return ""

        local_state = profile_dir / "Local State"
        key_file = str(local_state) if local_state.is_file() else None

        try:
            import browser_cookie3 as bc3
        except ImportError:
            logger.error("browser_cookie3 is not installed.")
            return ""

        try:
            jar = bc3.chromium(
                cookie_file=str(cookie_db),
                domain_name="vinted",
                key_file=key_file,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chromium profile cookie read failed: %s", exc)
            return ""

        parts: list[str] = []
        for c in jar:
            dom = (getattr(c, "domain", "") or "").lower().lstrip(".")
            if "vinted" not in dom.replace(".", ""):
                continue
            name = getattr(c, "name", None)
            value = getattr(c, "value", None)
            if name and value is not None:
                parts.append(f"{name}={value}")
        header = "; ".join(parts)
        if header:
            logger.info("Read Vinted cookies from disk profile (%s entries).", len(parts))
        return header
