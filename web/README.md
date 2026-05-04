# GoupixDex Web + Desktop UI (Nuxt 4 + Tauri)

Single frontend shared between:

- the **web** version (Nuxt 4),
- the **desktop** version (Tauri, Windows + macOS) — required for **Vinted** features (publishing + wardrobe sync).

## Pages overview

| Route                       | Access    | Purpose                                                                                                              |
| --------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------- |
| `/`                         | Public    | Marketing landing (Vinted + eBay + wardrobe sync pitch).                                                             |
| `/request`                  | Public    | Submit an access request (`POST /access-requests`).                                                                  |
| `/login`                    | Public    | JWT sign-in (rejects `pending` / `rejected` / `banned`).                                                             |
| `/setup-password/[token]`   | Public    | One-time password setup from an admin-issued link.                                                                   |
| `/dashboard`                | Auth      | KPIs, revenue timeline, channel split (Vinted vs eBay).                                                              |
| `/articles`, `/articles/**` | Auth      | Inventory CRUD, scan flow, batch publish.                                                                            |
| `/settings`                 | Auth      | Profile, notifications, security.                                                                                    |
| `/settings/marketplaces`    | Auth      | Toggle Vinted/eBay, link Vinted account (`VintedAccountCard`), eBay OAuth + onboarding.                              |
| `/users`                    | **Admin** | User list (avatar via PokeAPI, status, margin, Vinted/eBay flags) + approve / reject / ban / generate password link. |
| `/downloads`                | Auth      | Download the Tauri desktop bundle (Windows / macOS).                                                                 |

The **admin** is the user seeded from the API (`SEED_USER_EMAIL`). The sidebar conditionally shows the _Utilisateurs_ link when `is_admin` is true (`useAuth().user`). Admin-only pages are guarded by [`app/middleware/admin.ts`](app/middleware/admin.ts).

## Vinted behavior

- **Web**: Vinted publishing & wardrobe sync are disabled — the UI points users to `/downloads`.
- **Desktop (Tauri)**: Vinted features call the local Python worker on `127.0.0.1:18766` (configurable via `NUXT_PUBLIC_VINTED_LOCAL_BASE`). Composables: `useVintedPublishStream`, `useVintedBatchStream`, `useWardrobeLocalSync`, `useWardrobeSyncStream`. The runtime is detected through the Tauri WebView. In `tauri:dev`, the app uses `127.0.0.1:18767` by default to avoid conflicts with an installed desktop app.
  - The desktop installer bundles the worker as a **PyInstaller sidecar** (`bundle.externalBin = ["binaries/goupix-vinted-worker"]`). End users do **not** need a system-wide Python install.
  - The worker is spawned by `web/src-tauri/src/lib.rs` on app startup and killed on exit. In dev (`tauri:dev`), `lib.rs` falls back to `python desktop_vinted_server.py` from the local `api/` folder so you can iterate without rebuilding the sidecar (set `GOUPIX_PYTHON` to override the interpreter).
  - Worker logs are written to `%LOCALAPPDATA%\GoupixDex\logs\vinted-worker.log` (Windows) / `~/Library/Logs/GoupixDex/vinted-worker.log` (macOS) so they survive `--noconsole` PyInstaller mode.
- **Amazon invites (desktop)**: the `desktop_amazon_server.py` worker listens on `127.0.0.1:18768` by default (`NUXT_PUBLIC_AMAZON_LOCAL_BASE`, `GOUPIX_AMAZON_LOCAL_PORT`). Like Vinted, **Tauri starts** the `goupix-amazon-worker` sidecar on launch (`bundle.externalBin`); in `tauri:dev`, with the repo cloned next to `web/`, it runs `python api/desktop_amazon_server.py`. `npm run tauri:dev` runs `desktop-workers:stubs` (empty placeholder files required by Tauri to validate both binaries before build).

## Browser requirement (desktop)

The Vinted worker drives a **Chrome** install via [`nodriver`](https://github.com/ultrafunkamsterdam/nodriver). At app startup the Tauri command `check_browser_availability` (Rust, see `lib.rs`) probes the standard install paths and:

- if **Chrome** is found → it is passed to the worker via `VINTED_CHROME_EXECUTABLE`,
- otherwise if **Edge** is found (always present on Win 10/11) → Edge is used as a fallback,
- otherwise the frontend mounts [`BrowserMissingModal.vue`](app/components/BrowserMissingModal.vue) (composable: [`useBrowserAvailability`](app/composables/useBrowserAvailability.ts)) blocking the UI until the user installs Chrome.

## Prerequisites

- Node.js 22+
- npm 10+
- For local Tauri: Rust toolchain installed

## Installation

```bash
npm install
```

The `prepare` script configures Git to use hooks from `web/.husky` (monorepo root: `.git` is above `web/`). After install, `git config core.hooksPath` should be `web/.husky`.

## Lint, format, typecheck

Same toolchain as `integrations/prepeers-front-b2b`: Prettier, ESLint (flat config + `@nuxt/eslint`), `vue-tsc`. See [`CONTEXT/CODE_STANDARDS.md`](CONTEXT/CODE_STANDARDS.md).

| Script                                              | Purpose                                      |
| --------------------------------------------------- | -------------------------------------------- |
| `npm run lint`                                      | Prettier check → ESLint → `vue-tsc --noEmit` |
| `npm run lint:fix`                                  | Prettier write + ESLint `--fix`              |
| `npm run lint:prettier` / `lint:eslint` / `lint:ts` | Single step                                  |
| `npm run typecheck`                                 | `nuxt typecheck` (Nuxt wrapper)              |

Pre-commit runs `npm run lint` (from `web/`). Commit messages are checked with **commitlint** (`commitlint.json`, conventional commits).

## Environment variables

Example in `.env.example`:

- `NUXT_PUBLIC_SITE_URL`: canonical site URL (used for SEO + sitemap).
- `NUXT_PUBLIC_API_BASE`: remote GoupixDex API URL (prod or local).
- `NUXT_PUBLIC_VINTED_LOCAL_BASE`: local desktop worker URL (default `http://127.0.0.1:18766`, Tauri only).
- `NUXT_PUBLIC_AMAZON_LOCAL_BASE`: local Amazon worker (default `http://127.0.0.1:18768`, Tauri / Amazon invites page).
- `NUXT_PUBLIC_GITHUB_REPO`: `owner/repo` slug for the `/downloads` page.
- `NUXT_PUBLIC_DESKTOP_RELEASE_CHANNEL`: `latest` or a GitHub Release tag.
- `NUXT_PUBLIC_GITHUB_API_BASE`: GitHub API base (default `https://api.github.com`).

## Web development

```bash
npm run dev
```

## Build web

```bash
npm run build
```

## Desktop version (Tauri)

### Dev desktop

```bash
npm run tauri:dev
```

The script first runs `desktop-workers:stubs` (`vinted-worker:stub` + `amazon-worker:stub`), which writes empty placeholders under `web/src-tauri/binaries/` for **both** `goupix-vinted-worker-<triple>(.exe)` and `goupix-amazon-worker-<triple>(.exe)` so Tauri’s `bundle.externalBin` validation passes. In `cfg(debug_assertions)` builds, `lib.rs` ignores the placeholders and spawns `python desktop_vinted_server.py` and `python desktop_amazon_server.py` from `api/` when those files exist. The folder `web/src-tauri/binaries/` is `.gitignore`d.

If you run `cargo check` / `cargo build` in `src-tauri` without `npm run tauri:dev`, run `npm run desktop-workers:stubs` first (otherwise the Tauri build fails: missing `externalBin` files).

To avoid collisions with a production desktop app running at the same time, `tauri:dev` defaults to:

- frontend local worker base: `http://127.0.0.1:18767`
- worker listening port: `18767`
- nodriver profile directory (outside the repo): on Windows `%LOCALAPPDATA%\GoupixDex\vinted-nodriver-profile-dev` (see `dev_vinted_nodriver_user_data_dir` in `web/src-tauri/src/lib.rs`)

If you see a Cargo error like:

`this version of Cargo is older than the 2024 edition`

update Rust/Cargo (Windows/macOS/Linux):

```bash
rustup self update
rustup update stable
rustup default stable
```

Then restart your terminal and check:

```bash
cargo -V
rustc -V
```

On Windows, if the version does not change, ensure `cargo` points to `~/.cargo/bin`:

```bash
where cargo
where rustc
```

### Build desktop

```bash
npm run tauri:build
```

The command first builds the Nuxt frontend in desktop mode (`NUXT_DESKTOP_BUILD=1`), then bundles the app with Tauri.

The desktop bundle ships two PyInstaller sidecars: `goupix-vinted-worker` (`api/desktop_vinted_server.spec`) and `goupix-amazon-worker` (`api/desktop_amazon_server.spec`) — see the _CI/CD_ section for per-OS steps.

## CI/CD

- `deploy-web.yml` — web build and deploy (Nitro + PM2).
- `deploy-api.yml` — backend build / VPS deployment (systemd + Xvfb for Vinted).
- `desktop-release.yml` — Windows/macOS desktop **release** builds (Windows binary without console) and a stable GitHub Release **per version** (`v0.1.x`, not prerelease). For each OS the workflow sets up Python 3.11, installs `api/requirements.txt` + PyInstaller, then runs `pyinstaller desktop_vinted_server.spec` **and** `pyinstaller desktop_amazon_server.spec` to produce `goupix-vinted-worker-<rust-triple>(.exe)` and `goupix-amazon-worker-<rust-triple>(.exe)` under `web/src-tauri/binaries/` before invoking `tauri-action`. Both macOS targets (`x86_64-apple-darwin` and `aarch64-apple-darwin`) run on `macos-latest` (Apple Silicon); the Intel job uses `actions/setup-python` with `architecture: x64` so PyInstaller runs under Rosetta 2 (preinstalled on GitHub macOS runners) and produces a native Intel sidecar.

## Tauri updater: key generation and GitHub secrets

From the `web/` folder, generate the keypair:

```bash
npx @tauri-apps/cli signer generate -w goupixdex.key
```

Read the private key (to copy into a GitHub secret):

```bash
cat goupixdex.key
```

If you are using PowerShell:

```powershell
Get-Content .\goupixdex.key -Raw
```

Then configure these 3 secrets in `GitHub > Settings > Secrets and variables > Actions`:

- `TAURI_SIGNING_PRIVATE_KEY`
  - Value: full contents of `goupixdex.key` (Tauri/minisign format, as-is, including line breaks).
  - Note: it is normal not to have `BEGIN PRIVATE KEY` / `END PRIVATE KEY`.
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
  - Value: the password entered during `signer generate`.
- `TAURI_UPDATER_PUBKEY`
  - Value: the public key generated by the command (`signer generate`) or the contents of `goupixdex.key.pub`.

Important:

- Never commit `goupixdex.key` or `goupixdex.key.pub`.
- Keep `goupixdex.key` in a secure location (secret manager, vault, etc.).
