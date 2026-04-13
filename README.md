<p align="center">
  <a href="https://goupixdex.dibodev.fr/">
    <img src="web/assets/images/logo-goupix-dev-256x256.png" alt="GoupixDex" width="160" />
  </a>
</p>

# GoupixDex

**GoupixDex** is a personal Pokémon TCG tool that scans cards via OCR, auto-generates Vinted listings, and tracks collection data. It integrates Cardmarket / TCGPlayer prices (via [PokéWallet](https://api.pokewallet.io)) to suggest profitable listings and provides a dashboard with sales, profits, and inventory stats.

**Live app:** [https://goupixdex.dibodev.fr/](https://goupixdex.dibodev.fr/)

## Repository layout

| Path | Description |
|------|-------------|
| [`web/`](web/) | Nuxt frontend (dashboard, articles, scan flow) — see [**Web README**](web/README.md) |
| [`api/`](api/) | FastAPI backend (auth, OCR, pricing, articles, optional Vinted automation) — see [**API README**](api/README.md) |
| [`o2switch-proxy/`](o2switch-proxy/) | Optional HTTP proxy for PokéWallet when the API host is blocked by upstream network rules |

## Features (high level)

- **Scan & OCR** — Upload card photos; Groq vision extracts set code, number, and metadata for pricing and titles.
- **Pricing** — PokéWallet-backed Cardmarket (EUR) and TCGPlayer (USD) signals, with configurable margin.
- **Inventory** — Articles CRUD, images (e.g. Supabase), sold state and sell price.
- **Vinted** — Optional automated listing creation (see API docs for credentials and limitations).
- **Dashboard** — Revenue, profit, and inventory-oriented views.

## Tech stack (overview)

- **Frontend:** Nuxt, Nuxt UI, Vue 3  
- **Backend:** FastAPI, SQLAlchemy, MariaDB/MySQL, JWT auth  
- **Integrations:** Groq (vision), PokéWallet (prices), optional Vinted automation

For setup, environment variables, and run commands, use the dedicated guides:

- **[`web/README.md`](web/README.md)** — install, `pnpm dev`, build  
- **[`api/README.md`](api/README.md)** — Python venv, migrations, `uvicorn`, Docker, API endpoints  

---

*Internal / personal project; production URL and integrations may change.*
