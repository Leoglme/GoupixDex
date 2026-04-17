# GoupixDex — API (Python)

Backend for **GoupixDex**: Pokémon TCG scanning, pricing (PokéWallet), inventory articles, JWT auth, optional Vinted automation (nodriver), and optional **eBay** listing (OAuth + Inventory API — see [`EBAY.md`](EBAY.md)).

## Stack

- **FastAPI** + **Uvicorn** — REST API, OpenAPI/Swagger at `/docs`
- **SQLAlchemy 2** ORM — models under `models/` (not Pydantic)
- **MariaDB / MySQL** — via **PyMySQL** (`mysql+pymysql://…`)
- **JWT** (python-jose) + **bcrypt**
- **Pydantic** — request/response validation only (`schemas/`)
- **Custom SQL migrations** in `migrations/` (no Alembic)
- **Docker Compose** — API (hot reload), MariaDB, phpMyAdmin

## Layout

```text
api/
  main.py                 # FastAPI app
  config.py               # AppSettings + legacy Vinted CLI defaults
  cli_vinted_listings.py  # Standalone nodriver CLI (was main.py)
  app_types/              # TypedDict (PokéWallet, Groq, Vinted payloads)
  core/
    database.py           # Engine, SessionLocal, get_db
    security.py           # JWT + password hashing
    deps.py               # Current user (Bearer)
  models/                 # SQLAlchemy ORM (User, Article, Image, MarginSettings)
  schemas/                # Pydantic API bodies only
  routes/                 # auth, users, articles, settings, scan
  services/
    ocr_service.py        # Groq vision wrapper
    pricing_service.py    # PokéWallet + EUR/USD average
    scan_service.py       # Title/description templates
    article_service.py
    auth_service.py
    vinted_publish_service.py  # Calls existing VintedService
    … (pokewallet, groq_vision_client, vinted_service, …)
  migrations/
  seeders/
```

## Requirements

- Python **3.10+**
- MariaDB or MySQL (local or Docker)
- Optional: `POKE_WALLET_API_KEY`, `GROQ_API_KEY`, **Chromium** for Vinted (see below)

### Vinted (Chromium) and Xvfb

Vinted publishing launches **Chromium** through **nodriver**. On a **headless machine** (VPS, container, CI), `VINTED_BROWSER_HEADLESS=false` requires a **DISPLAY**: this repository uses **Xvfb** so no manual display setup is needed.

| Environment | Behavior |
|----------------|---------------|
| **Docker Compose** (`api/`) | The image installs **chromium**, **xvfb**, and **xauth**; the service command wraps **uvicorn** with **`xvfb-run`**. No manual step required. |
| **GitHub → VPS deploy** (`.github/workflows/deploy-api.yml`) | `apt install` includes **xvfb** and **xauth**; the **systemd** unit runs Uvicorn under **`xvfb-run`**. |
| **Linux without Docker** (venv + custom systemd) | Install `xvfb` and `xauth` (`apt install xvfb xauth`), then run the API with: `xvfb-run -a --server-args="-screen 0 1920x1080x24" uvicorn …` when `VINTED_BROWSER_HEADLESS=false`. |
| **Windows (dev)** | No Xvfb needed; use `VINTED_BROWSER_HEADLESS=false` with a local desktop session, or use `run_dev.py` when running `--reload` with Vinted. |

**GitHub Actions (optional secret)**: `VINTED_BROWSER_HEADLESS` — if missing or empty, the value generated on the VPS remains **`true`** (historical behavior). Set **`false`** for a headed Chromium session on Xvfb (often less likely to be blocked by Vinted than built-in headless mode). **Cloudflare / hosting IPs** can still block requests: it is possible to get a **403** from `curl` on the VPS while a browser returns **200**.

Useful variables in `.env` / `.env.example`: `VINTED_BROWSER_HEADLESS`, `VINTED_CHROME_EXECUTABLE` (often `/usr/bin/chromium` on Linux).

**Windows / macOS (desktop app)**: with `VINTED_BROWSER_HEADLESS=false`, **`VINTED_BROWSER_DISCREET=true`** (default) keeps `--start-maximized`, then applies `--window-position` (off-screen) + `--start-minimized` to stay discreet while keeping a headed rendering path. You can disable minimization with `VINTED_BROWSER_DISCREET_MINIMIZE=false`. On **Linux + full-screen Xvfb**, set `VINTED_BROWSER_DISCREET=false` to keep standard behavior.

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

### Seeders (optional, dev)

1. **User** — set `SEED_USER_EMAIL` and `SEED_USER_PASSWORD` in `.env`, then:

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

### Main endpoints

| Method | Path | Notes |
|--------|------|--------|
| POST | `/auth/login` | JWT Bearer |
| POST | `/users` | Register |
| GET/PUT/DELETE | `/users`, `/users/{id}`, `/users/me` | Auth required for most |
| POST | `/scan-card` | Multipart image + optional `margin_percent`; OCR + pricing preview (no DB) |
| CRUD | `/articles` | Create uses multipart (fields + `images` files); then Vinted attempt |
| PATCH | `/articles/{id}/sold` | Mark sold + `sell_price` |
| GET/PUT | `/settings` | Margin % (default 20) |

**Vinted:** on `POST /articles`, publication uses the authenticated user's `vinted_email` and **encrypted** `vinted_password` (Fernet, key derived from `JWT_SECRET`). Legacy rows still holding a bcrypt hash cannot be decrypted—re-save the Vinted password via user settings or the seeder, or set `VINTED_EMAIL_OR_USERNAME` / `VINTED_PASSWORD` in the environment as fallback.

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
- The image includes **Chromium**, **Xvfb**, and **xauth**; `VINTED_*` and **Supabase** variables can be defined in a **`.env`** file next to `docker-compose.yml` (`${…}` substitution — see [Compose env files](https://docs.docker.com/compose/environment-variables/set-environment-variables/)).

Create a user after startup: `docker compose exec api python seeders/user_seeder.py` (with env vars set), or use `POST /users` and `POST /auth/login`.

### API deployment (GitHub → VPS)

The **Deploy API** workflow installs **xvfb** and **xauth**, writes the **systemd** unit with **`ExecStart=/usr/bin/xvfb-run … uvicorn`**, and can set **`VINTED_BROWSER_HEADLESS`** via the secret of the same name (default **`true`** when the secret is missing). No manual Xvfb installation is required on the VPS after deploying through this CI.

## Limitations

- Vinted UI and anti-bot policies may break automation; local runs that trigger publication need valid Vinted credentials.
- Average price mixes Cardmarket (EUR) and TCGPlayer (USD) using `USD_TO_EUR` in `config` (`AppSettings.usd_to_eur`).
