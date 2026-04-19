# GoupixDex — API (Python)

Backend for **GoupixDex**: Pokémon TCG scanning, pricing (PokéWallet), inventory articles, JWT auth, public **access requests + admin moderation**, **Vinted** publishing & wardrobe sync (nodriver, single or batch), and **eBay France** listing (per-user OAuth + Inventory API — see [`EBAY.md`](EBAY.md)).

## Stack

- **FastAPI** + **Uvicorn** — REST API, OpenAPI/Swagger at `/docs`
- **SQLAlchemy 2** ORM — models under `models/` (not Pydantic)
- **MariaDB / MySQL** — via **PyMySQL** (`mysql+pymysql://…`)
- **JWT** (python-jose) + **bcrypt** + **Fernet** (symmetric encryption for Vinted credentials and eBay tokens, key derived from `JWT_SECRET`)
- **Pydantic** — request/response validation only (`schemas/`)
- **Custom SQL migrations** in `migrations/` (no Alembic)
- **Docker Compose** — API (hot reload), MariaDB, phpMyAdmin

## Layout

```text
api/
  main.py                       # FastAPI app (routers + middleware)
  desktop_vinted_server.py      # Local HTTP worker (127.0.0.1:18766) for Tauri desktop:
                                #   Vinted publish + wardrobe sync via nodriver/Chromium
  config.py                     # AppSettings + legacy Vinted CLI defaults
  cli_vinted_listings.py        # Standalone nodriver CLI (legacy batch from items.json)
  app_types/                    # TypedDict (PokéWallet, Groq, Vinted, eBay payloads)
  core/
    database.py                 # Engine, SessionLocal, get_db
    security.py                 # JWT + password hashing + Fernet helpers
    deps.py                     # get_current_user / get_current_admin (Bearer or query token)
    win32_asyncio.py            # Force ProactorEventLoop on Windows (nodriver subprocesses)
  models/                       # SQLAlchemy ORM (User, Article, Image, MarginSettings)
  schemas/                      # Pydantic request/response bodies only
  routes/
    auth.py                     # /auth/login (blocks pending/rejected/banned)
    users.py                    # /users (admin) + /users/me + /users/me/vinted
    access_requests.py          # /access-requests (public + admin) + /password-setup/{token}
    articles.py                 # CRUD + /vinted-batch + /ebay-batch + SSE streams
    settings_route.py           # /settings (margin %, vinted_enabled, ebay_enabled, …)
    ebay_route.py               # /ebay/oauth/* + /ebay/onboarding/setup + /ebay/status
    pricing_route.py            # PokéWallet preview / suggestions
    stats_route.py              # /stats/dashboard (CA, marges, split Vinted/eBay)
    scan.py                     # /scan-card (multipart, OCR + pricing preview, no DB)
  services/
    ocr_service.py              # Groq vision wrapper
    pricing_service.py          # PokéWallet + EUR/USD average
    scan_service.py             # Title/description templates
    article_service.py
    auth_service.py
    access_request_service.py   # submit / approve / reject / ban / setup token
    vinted_publish_service.py
    vinted_batch_*.py           # Grouped Vinted publishing (one browser, sequential)
    vinted_progress_session_service.py
    vinted_chromium_profile_cookie_service.py
    desktop_vinted_runner_service.py
    desktop_wardrobe_sync_runner_service.py
    vinted_wardrobe/            # Wardrobe sync (catalog + sold + descriptions)
      goupix_vinted_wardrobe_sync_service.py
      vinted_catalog_service.py
      vinted_sold_items_service.py
      vinted_http_service.py
    wardrobe_job_store_service.py
    ebay_oauth_service.py       # Authorization URL + code exchange
    ebay_publish_service.py     # Inventory item + offer + publish
    ebay_seller_metadata_service.py
    ebay_onboarding_service.py  # FR location + business policies
    ebay_background_service.py
    combined_marketplace_service.py
    user_settings_service.py
    supabase_storage_service.py
    stats_service.py
    poke_wallet_*.py            # PokéWallet client + reference prices
    groq_vision_service.py
  migrations/                   # 001…005 (run via run_migrations.py)
  seeders/                      # user_seeder, margin_seeder, article_seeder, run_all
```

## Requirements

- Python **3.10+**
- MariaDB or MySQL (local or Docker)
- Optional: `POKE_WALLET_API_KEY`, `GROQ_API_KEY`, **Chromium** for Vinted (see below), `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` / `EBAY_REDIRECT_URI` for eBay

### Vinted (Chromium) and Xvfb

Vinted publishing launches **Chromium** through **nodriver**. On a **headless machine** (VPS, container, CI), `VINTED_BROWSER_HEADLESS=false` requires a **DISPLAY**: this repository uses **Xvfb** so no manual display setup is needed.

| Environment | Behavior |
|----------------|---------------|
| **Docker Compose** (`api/`) | The image installs **chromium**, **xvfb**, and **xauth**; the service command wraps **uvicorn** with **`xvfb-run`**. No manual step required. |
| **GitHub → VPS deploy** (`.github/workflows/deploy-api.yml`) | `apt install` includes **xvfb** and **xauth**; the **systemd** unit runs Uvicorn under **`xvfb-run`**. |
| **Linux without Docker** (venv + custom systemd) | Install `xvfb` and `xauth` (`apt install xvfb xauth`), then run the API with: `xvfb-run -a --server-args="-screen 0 1920x1080x24" uvicorn …` when `VINTED_BROWSER_HEADLESS=false`. |
| **Windows / macOS desktop** (Tauri) | Vinted publishing & wardrobe sync go through `desktop_vinted_server.py` on `127.0.0.1:18766`. No Xvfb needed — the user's local Chromium is used. |

**GitHub Actions (optional secret)**: `VINTED_BROWSER_HEADLESS` — if missing or empty, the value generated on the VPS remains **`true`** (historical behavior). Set **`false`** for a headed Chromium session on Xvfb (often less likely to be blocked by Vinted than built-in headless mode). **Cloudflare / hosting IPs** can still block requests: it is possible to get a **403** from `curl` on the VPS while a browser returns **200**.

Useful variables in `.env` / `.env.example`: `VINTED_BROWSER_HEADLESS`, `VINTED_CHROME_EXECUTABLE` (often `/usr/bin/chromium` on Linux), `VINTED_BROWSER_DISCREET*`.

**Windows / macOS (desktop app)**: with `VINTED_BROWSER_HEADLESS=false`, **`VINTED_BROWSER_DISCREET=true`** (default) keeps `--start-maximized`, then applies `--window-position` (off-screen) + `--start-minimized` to stay discreet while keeping a headed rendering path. Disable minimization with `VINTED_BROWSER_DISCREET_MINIMIZE=false`. On **Linux + full-screen Xvfb**, set `VINTED_BROWSER_DISCREET=false` to keep standard behavior.

## Install

```bash
cd api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set at least `DATABASE_URL` and `JWT_SECRET`.

### Database

```bash
python migrations/run_migrations.py
```

Migrations applied in order:

| File | Purpose |
|------|---------|
| `001_initial.sql` | `users`, `articles`, `images`, `settings` (margin) |
| `002_article_vinted_published.sql` | `articles.vinted_published_at` |
| `003_marketplaces_ebay.sql` | Vinted/eBay toggles, eBay tokens & policies |
| `004_article_sale_price.sql` | `articles.sell_price` + `sold_at` |
| `005_access_requests.sql` | `users.is_admin`, `status`, `request_message`, `password_setup_token`, password nullable |

### Seeders (optional, dev)

1. **User** — set `SEED_USER_EMAIL` and `SEED_USER_PASSWORD` in `.env`. The seeder always marks this account as **admin + approved** (idempotent on re-run):

   ```bash
   python seeders/user_seeder.py
   ```

2. **Margin (20% default)** — creates a `settings` row for any user that does not have one yet:

   ```bash
   python seeders/margin_seeder.py
   ```

   Override default percent with `SEED_MARGIN_PERCENT` (e.g. `25`).

3. **Fake articles** — requires an existing user. Uses `SEED_ARTICLE_USER_EMAIL` or falls back to `SEED_USER_EMAIL`. Deletes previous `[DEV] …` titles for that user, then inserts four sample articles (one marked sold):

   ```bash
   python seeders/article_seeder.py
   ```

4. **Everything in order** (same env vars as above):

   ```bash
   python seeders/run_all.py
   ```

## Run API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On **Windows**, if you use **`--reload`** with **Vinted** publishing (nodriver / Chrome), uvicorn can pick an event loop without subprocess support → `NotImplementedError` in nodriver. Use instead:

```bash
python run_dev.py
```

or explicitly (Windows only — stdlib `ProactorEventLoop` class):

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio.windows_events:ProactorEventLoop
```

- Swagger UI: http://127.0.0.1:8000/docs
- Health: `GET /health`
- Article images are stored in **Supabase Storage** (public URLs in DB).

### Local desktop worker (Tauri only)

The Tauri desktop bundle launches a second FastAPI process on the user's machine to keep nodriver / Chromium **off the production VPS**:

```bash
python desktop_vinted_server.py
```

| Variable | Default | Role |
|----------|---------|------|
| `GOUPIX_VINTED_LOCAL_PORT` | `18766` | Port listening on `127.0.0.1` (Tauri dev overrides to `18767` by default to avoid conflicts with installed desktop app) |
| `GOUPIX_REMOTE_API` | (none) | Remote API URL (used when the client does not send `X-Goupix-Remote-Api`) |

It exposes job-style endpoints used by the Nuxt frontend (`useWardrobeLocalSync`, `useVintedPublishStream`, `useVintedBatchStream`, `useWardrobeSyncStream`):

- `POST /vinted/wardrobe-sync/jobs` + `GET /vinted/wardrobe-sync/jobs/{id}` (poll)
- `GET  /vinted/wardrobe-sync/jobs/{id}/stream` (SSE log stream)
- `POST /vinted/publish/jobs` + SSE stream for grouped/single Vinted publishes
- Vinted listing image proxy (Vinted CDN hosts only)

### Main endpoints

| Method | Path | Notes |
|--------|------|--------|
| POST | `/auth/login` | JWT Bearer; rejects `pending`, `rejected`, `banned` |
| POST | `/access-requests` | **Public** — submit a `/request` (creates a `pending` user) |
| POST | `/access-requests/{id}/approve` \| `/reject` \| `/ban` | **Admin only** |
| POST | `/access-requests/{id}/password-link` | **Admin only** — issues a one-time setup token |
| GET / POST | `/password-setup/{token}` | **Public** — fetch info / set password (token consumed) |
| GET | `/users` | **Admin only** — list with margin %, Vinted/eBay flags, status |
| POST / DELETE | `/users`, `/users/{id}` | **Admin only** for create/delete |
| GET / PUT | `/users/me`, `/users/{id}` | Self for own row |
| PUT | `/users/me/vinted` | Self-service: link/update encrypted Vinted credentials |
| GET | `/users/me/vinted-decrypted` | Plaintext Vinted creds for the local desktop worker |
| GET / PUT | `/settings` | Margin % (default 20), `vinted_enabled`, `ebay_enabled`, eBay listing config |
| POST | `/scan-card` | Multipart image + optional `margin_percent`; OCR + pricing preview (no DB) |
| CRUD | `/articles` | Create uses multipart (fields + `images` files); auto Vinted/eBay attempt |
| PATCH | `/articles/{id}/sold` | Mark sold + `sell_price` |
| POST | `/articles/vinted-batch` + SSE | Grouped Vinted publishing (single browser, sequential) |
| POST | `/articles/ebay-batch`            | Sequential eBay Inventory publishing |
| GET | `/ebay/oauth/authorize-url` | Build the consent URL (per-user OAuth state) |
| POST | `/ebay/oauth/exchange` \| `/disconnect` | Store / clear encrypted tokens on the user row |
| POST | `/ebay/onboarding/setup` | Create FR inventory location + business policies |
| POST | `/ebay/policies/fulfillment/ensure` | Create/update « GoupixDex — Envoi » shipping policy |
| GET | `/ebay/status` \| `/ebay/seller-setup` | Connection state and metadata |
| GET | `/stats/dashboard` | KPIs, revenue timeline, channel split |

**Vinted credentials:** on `POST /articles`, publication uses the authenticated user's `vinted_email` and **encrypted** `vinted_password` (Fernet, key derived from `JWT_SECRET`). Legacy rows still holding a bcrypt hash cannot be decrypted — re-save the Vinted password from **Settings → Marketplace** (`VintedAccountCard`), the seeder, or `PUT /users/me/vinted`. As a last-resort fallback, set `VINTED_EMAIL_OR_USERNAME` / `VINTED_PASSWORD` in the environment.

**eBay credentials:** see [`EBAY.md`](EBAY.md). Refresh and access tokens are stored encrypted on the user row; `ensure_ebay_access_token` refreshes silently when expired.

### Access requests & admin flow

1. A visitor submits `/request` (email + optional message) → backend creates a user with `status='pending'`, no password.
2. The seeded admin (`SEED_USER_EMAIL`) sees the request in `/users`.
3. Admin can **approve / reject / ban** the user, or **generate a one-time password setup link** that the user opens at `/setup-password/{token}`.
4. Once consumed, the token is invalidated and the user can sign in with their new password.

### Legacy Vinted CLI (batch `items.json`)

```bash
python cli_vinted_listings.py
```

Uses `config.py` listing defaults and `items.json` / `images/` at the project root.

## Docker

From `api/`:

```bash
docker compose up --build
```

- API: port **8000** (migrations + optional seed at startup, then **uvicorn** under **`xvfb-run`** for Vinted)
- MariaDB: **3306**
- phpMyAdmin: **8080**
- The image includes **Chromium**, **Xvfb**, and **xauth**; `VINTED_*`, `EBAY_*`, and **Supabase** variables can be defined in a **`.env`** file next to `docker-compose.yml` (`${…}` substitution — see [Compose env files](https://docs.docker.com/compose/environment-variables/set-environment-variables/)).

Create the admin user after startup: `docker compose exec api python seeders/user_seeder.py` (with env vars set), or use `POST /access-requests` and let the seeded admin approve and issue a password link.

### API deployment (GitHub → VPS)

The **Deploy API** workflow installs **xvfb** and **xauth**, writes the **systemd** unit with **`ExecStart=/usr/bin/xvfb-run … uvicorn`**, and can set **`VINTED_BROWSER_HEADLESS`** via the secret of the same name (default **`true`** when the secret is missing). No manual Xvfb installation is required on the VPS after deploying through this CI.

## Limitations

- Vinted UI and anti-bot policies may break automation; production VPS deployments often hit Cloudflare / IP rate limits — the desktop worker (Tauri) is the recommended path for Vinted.
- Wardrobe sync requires a valid Vinted session cookie (captured via the local nodriver run, or `VINTED_COOKIE` env var as fallback).
- Average price mixes Cardmarket (EUR) and TCGPlayer (USD) using `USD_TO_EUR` in `config` (`AppSettings.usd_to_eur`).
- eBay sandbox requires test buyer/seller accounts and category/policy IDs valid for the chosen marketplace (default `EBAY_FR`).
