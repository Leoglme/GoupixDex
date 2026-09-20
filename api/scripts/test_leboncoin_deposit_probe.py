"""
Probe Leboncoin deposit form DOM (local dev). Usage from api/:
  python scripts/test_leboncoin_deposit_probe.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# api/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.win32_asyncio import ensure_proactor_event_loop
from services.leboncoin_service import LeboncoinService, DEPOSIT_URL

ensure_proactor_event_loop()

PROBE_JS = """
JSON.stringify((() => {
  const inputs = [...document.querySelectorAll('input, textarea, select, button')].slice(0, 100);
  return inputs.map(el => ({
    tag: el.tagName,
    type: el.type || null,
    name: el.getAttribute('name'),
    id: el.id || null,
    qa: el.getAttribute('data-qa-id'),
    placeholder: el.getAttribute('placeholder'),
    aria: el.getAttribute('aria-label'),
    text: el.tagName === 'BUTTON' ? (el.textContent || '').trim().slice(0, 60) : null,
  }));
})())
"""


async def main() -> None:
    await LeboncoinService.init_browser()
    try:
        tab = await LeboncoinService._browser.get(DEPOSIT_URL)  # type: ignore[union-attr]
        await tab.sleep(2.5)
        url = await tab.evaluate("location.href", return_by_value=True)
        title = await tab.evaluate("document.title", return_by_value=True)
        fields_raw = await tab.evaluate(PROBE_JS, return_by_value=True)
        fields = json.loads(fields_raw) if isinstance(fields_raw, str) else fields_raw
        print("URL:", url)
        print("Title:", title)
        out_path = Path(__file__).resolve().parent / "leboncoin_probe_output.json"
        out_path.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Wrote", out_path, "count=", len(fields) if isinstance(fields, list) else "?")
        auth = await LeboncoinService._current_url(tab)
        print("Login redirect?", "connexion" in str(auth).lower())
    finally:
        LeboncoinService.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
