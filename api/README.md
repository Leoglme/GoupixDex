# GoupixDex — API (Python)

Backend for **GoupixDex**: Pokémon TCG scanning, pricing (PokéWallet), inventory articles, JWT auth, and optional Vinted automation (nodriver).

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
- Optional: `POKE_WALLET_API_KEY`, `GROQ_API_KEY`, **Chromium** for Vinted (voir ci-dessous)

### Vinted (Chromium) et Xvfb

La publication Vinted lance **Chromium** via **nodriver**. Sur une machine **sans écran** (VPS, conteneur, CI), `VINTED_BROWSER_HEADLESS=false` exige un **DISPLAY** : le dépôt prévoit **Xvfb** pour ne rien configurer à la main.

| Environnement | Comportement |
|----------------|---------------|
| **Docker Compose** (`api/`) | L’image installe **chromium**, **xvfb**, **xauth** ; la commande de service enveloppe **uvicorn** avec **`xvfb-run`**. Aucune étape manuelle. |
| **Déploiement GitHub → VPS** (`.github/workflows/deploy-api.yml`) | `apt install` inclut **xvfb** et **xauth** ; l’unité **systemd** lance Uvicorn sous **`xvfb-run`**. |
| **Linux sans Docker** (venv + systemd maison) | Installez `xvfb` et `xauth` (`apt install xvfb xauth`), puis lancez l’API avec : `xvfb-run -a --server-args="-screen 0 1920x1080x24" uvicorn …` si `VINTED_BROWSER_HEADLESS=false`. |
| **Windows (dev)** | Pas besoin d’Xvfb ; utilisez `VINTED_BROWSER_HEADLESS=false` avec un bureau local, ou `run_dev.py` si vous utilisez `--reload` avec Vinted. |

**GitHub Actions (secret optionnel)** : `VINTED_BROWSER_HEADLESS` — si absent ou vide, la valeur générée sur le VPS reste **`true`** (comportement historique). Mettez **`false`** pour un Chromium fenêtré sur Xvfb (souvent moins refusé par Vinted que le headless intégré). **Cloudflare / IP hébergeur** peuvent quand même bloquer des requêtes : un `curl` en **403** depuis le VPS alors qu’un navigateur répond **200** est possible.

Variables utiles dans `.env` / `.env.example` : `VINTED_BROWSER_HEADLESS`, `VINTED_CHROME_EXECUTABLE` (souvent `/usr/bin/chromium` sous Linux).

**Windows / macOS (app desktop)** : avec `VINTED_BROWSER_HEADLESS=false`, le mode **`VINTED_BROWSER_DISCREET=true`** (défaut) garde `--start-maximized`, puis applique `--window-position` (hors écran) + `--start-minimized` pour rester discret tout en gardant un rendu "headed". Vous pouvez désactiver la minimisation via `VINTED_BROWSER_DISCREET_MINIMIZE=false`. Sur **Linux + Xvfb plein écran**, mettre `VINTED_BROWSER_DISCREET=false` pour garder le comportement standard.

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

Sous **Windows**, si vous utilisez **`--reload`** et la publication **Vinted** (nodriver / Chrome), uvicorn choisit une boucle sans support des sous-processus → erreur `NotImplementedError` dans nodriver. Utilisez plutôt :

```bash
python run_dev.py
```

ou explicitement (Windows uniquement — la classe stdlib `ProactorEventLoop`) :

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

- API: port **8000** (migrations + seed conditionnel au démarrage, puis **uvicorn** sous **`xvfb-run`** pour Vinted)
- MariaDB: **3306**
- phpMyAdmin: **8080**
- L’image inclut **Chromium**, **Xvfb** et **xauth** ; les variables `VINTED_*` et **Supabase** peuvent être définies dans un fichier **`.env`** à côté de `docker-compose.yml` (substitution `${…}` — voir [Compose env files](https://docs.docker.com/compose/environment-variables/set-environment-variables/)).

Create a user after startup: `docker compose exec api python seeders/user_seeder.py` (with env vars set), or use `POST /users` and `POST /auth/login`.

### Déploiement API (GitHub → VPS)

Le workflow **Deploy API** installe **xvfb** et **xauth**, écrit l’unité **systemd** avec **`ExecStart=/usr/bin/xvfb-run … uvicorn`**, et peut fixer **`VINTED_BROWSER_HEADLESS`** via le secret du même nom (défaut **`true`** si le secret est absent). Aucune installation manuelle de Xvfb sur le VPS n’est nécessaire après un déploiement via cette CI.

## Limitations

- Vinted UI and anti-bot policies may break automation; local runs that trigger publication need valid Vinted credentials.
- Average price mixes Cardmarket (EUR) and TCGPlayer (USD) using `USD_TO_EUR` in `config` (`AppSettings.usd_to_eur`).
