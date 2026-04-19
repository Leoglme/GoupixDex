<p align="center">
  <a href="https://goupixdex.dibodev.fr/">
    <img src="web/assets/images/logo-goupix-dev-256x256.png" alt="GoupixDex" width="160" />
  </a>
</p>

# GoupixDex

**GoupixDex** is a personal Pokémon TCG tool that scans cards via OCR, auto-generates marketplace listings (**Vinted** + **eBay France**), synchronises your **Vinted wardrobe** (active listings, sold items, descriptions), and tracks collection data. It integrates Cardmarket / TCGPlayer prices (via [PokéWallet](https://api.pokewallet.io)) to suggest profitable listings and provides a dashboard with sales, profits, channel split, and inventory stats.

**Live app:** [https://goupixdex.dibodev.fr/](https://goupixdex.dibodev.fr/)

## Repository layout

| Path | Description |
|------|-------------|
| [`web/`](web/) | Nuxt 4 frontend + Tauri desktop shell (dashboard, articles, scan flow, admin) — see [**Web README**](web/README.md) |
| [`api/`](api/) | FastAPI backend (auth, OCR, pricing, articles, access requests, Vinted automation, eBay) — see [**API README**](api/README.md) |
| [`o2switch-proxy/`](o2switch-proxy/) | Optional HTTP proxy for PokéWallet when the API host is blocked by upstream network rules |

## Features (high level)

- **Scan & OCR** — Upload card photos; Groq vision extracts set code, number, and metadata for pricing and titles.
- **Pricing** — PokéWallet-backed Cardmarket (EUR) and TCGPlayer (USD) signals, with configurable margin.
- **Inventory** — Articles CRUD with Supabase-stored images, sold state, and sell price.
- **Vinted publishing** — Optional automated listing creation (single or grouped batch), runs through a local desktop worker (Tauri) using nodriver / Chromium. Each user stores their own encrypted Vinted credentials in Settings → Marketplace.
- **Vinted wardrobe sync** — Pulls the user's active listings, sold items, and HTML descriptions from Vinted (via the local desktop worker) and surfaces them in GoupixDex.
- **eBay (France)** — Optional listing via the eBay Inventory API (per-user OAuth, automated business policies and inventory location). Setup guide: [`api/EBAY.md`](api/EBAY.md).
- **Dashboard** — Revenue, profit, channel split (Vinted vs eBay), and inventory views.
- **Access requests & admin** — Public `/request` page; the seeded user (`SEED_USER_EMAIL`) is the sole admin and approves / rejects / bans requests and issues one-time password setup links from `/users`.

## Tech stack (overview)

- **Frontend:** Nuxt 4, Nuxt UI, Vue 3, Tauri (Windows + macOS desktop bundle)
- **Backend:** FastAPI, SQLAlchemy 2, MariaDB/MySQL, JWT auth, custom SQL migrations
- **Integrations:** Groq (vision), PokéWallet (prices), Vinted (nodriver / Chromium), eBay Sell APIs (Inventory + Account), Supabase Storage

For setup, environment variables, and run commands, use the dedicated guides:

- **[`web/README.md`](web/README.md)** — install, `npm run dev`, build, Tauri desktop
- **[`api/README.md`](api/README.md)** — Python venv, migrations, `uvicorn`, Docker, API endpoints
- **[`api/EBAY.md`](api/EBAY.md)** — eBay developer keys, RuName, OAuth and onboarding

---

*Internal / personal project; production URL and integrations may change.*
