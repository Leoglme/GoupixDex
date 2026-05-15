"""
One-shot diagnostic for ``ebay_sold_scrape_service``.

Fetches the same URL the production service uses, dumps the HTML to
``/tmp/ebay-sold.html``, and reports how many elements match candidate
selectors so we can pick the right one when eBay rotates its SRP layout.

Run from the ``api/`` directory:

    python -m scripts.debug_ebay_scrape "carte pokemon"
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from services.ebay_sold_scrape_service import (
    _parse_sold_rows,
    fetch_sold_listings_html,
)

OUT = Path("/tmp/ebay-sold.html")

#: Candidate selectors to probe. Order is informational; we report counts for all.
_CANDIDATE_SELECTORS = (
    "li.s-item",
    "ul.srp-results > li",
    ".srp-results .s-item",
    ".srp-results .s-item__wrapper",
    "li.s-item__pl-on-bottom",
    "[data-testid='srp-results'] li",
    "[data-view*='mi:1686'] li",
    "ul.b-list__items_nofooter li",
    "li[data-viewport]",
    "div.s-card",
)

#: Selectors that often hold the relative/absolute « sold » caption.
_CAPTION_SELECTORS = (
    ".s-item__caption--signal",
    ".s-item__title--tagblock",
    ".s-item__subtitle",
    ".s-card__caption",
    "[class*='caption']",
)


async def main(q: str) -> None:
    html = await fetch_sold_listings_html(q=q, page_size=50)
    OUT.write_text(html, encoding="utf-8")
    print(f"saved html ({len(html)} bytes) → {OUT}")

    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("title")
    print(f"<title>: {title.get_text(strip=True) if title else '(none)'}")

    h1 = soup.select_one("h1")
    print(f"<h1>: {h1.get_text(' ', strip=True)[:120] if h1 else '(none)'}")

    # Quick consent-page heuristic
    consent_markers = ("consent", "consentement", "accepter", "vos choix")
    head_excerpt = html[:4000].lower()
    if any(tok in head_excerpt for tok in consent_markers):
        print("⚠️  consent-related token found in first 4 KB — possible CMP page")

    print("\n-- selector probe --")
    for sel in _CANDIDATE_SELECTORS:
        try:
            n = len(soup.select(sel))
        except Exception as exc:  # invalid selector etc.
            n = f"ERR({exc})"
        print(f"  {sel:55s} → {n}")

    print("\n-- existing parser --")
    rows = _parse_sold_rows(html)
    print(f"  _parse_sold_rows: {len(rows)} rows")
    for r in rows[:3]:
        print(f"    title={r.title[:60]!r}  caption={r.sold_caption!r}  hours_ago={r.approx_hours_ago}")

    # If selector probe found something useful, sample captions
    print("\n-- sample captions from first li.s-item or fallback --")
    sample_lis = soup.select("li.s-item") or soup.select("li.s-item__pl-on-bottom") or soup.select("ul.srp-results > li")
    for i, li in enumerate(sample_lis[:5]):
        for csel in _CAPTION_SELECTORS:
            cap = li.select_one(csel)
            if cap:
                print(f"  li#{i} via {csel}: {cap.get_text(' ', strip=True)[:120]!r}")
                break
        else:
            print(f"  li#{i} (no caption matched any selector)")

    # Field probes on the first 2 LIs so we can pin down the new s-card selectors
    field_probes: dict[str, tuple[str, ...]] = {
        "title": (
            ".s-card__title", ".s-card__title-link",
            "[role='heading']", "[role=heading]",
            "a .su-styled-text", ".s-item__title", ".s-item__title span",
        ),
        "price": (".s-card__price", ".s-item__price", "[class*='price']"),
        "link": ("a.su-link", "a[href*='/itm/']", "a.s-item__link"),
        "image": (
            ".s-card__image img", ".s-card__image-wrapper img",
            "img.s-item__image-img", ".image-treatment img", "img",
        ),
        "caption": _CAPTION_SELECTORS,
    }

    print("\n-- field selector probe (first 2 LIs) --")
    for i, li in enumerate(sample_lis[:2]):
        print(f"\n[li #{i}]")
        for field, sels in field_probes.items():
            for s in sels:
                el = li.select_one(s)
                if not el:
                    continue
                if field == "link":
                    snippet = (el.get("href") or "")[:120]
                elif field == "image":
                    snippet = (el.get("src") or el.get("data-src") or "")[:120]
                else:
                    snippet = el.get_text(" ", strip=True)[:120]
                print(f"  {field:7s} via {s:35s} → {snippet!r}")
                break
            else:
                print(f"  {field:7s} no match")
        # Also dump the LI's outer HTML head (200 chars) so we can see attributes
        outer = str(li)[:300].replace("\n", " ")
        print(f"  outer[:300]: {outer}")


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "carte pokemon"
    asyncio.run(main(query))
