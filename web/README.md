# GoupixDex Web + Desktop UI (Nuxt 4 + Tauri)

Frontend unique partagé entre :

- la version **web** (Nuxt 4),
- la version **desktop** (Tauri, Windows + macOS).

## Prérequis

- Node.js 22+
- npm 10+
- Pour Tauri local : Rust toolchain installé

## Installation

```bash
npm install
```

## Variables d’environnement

Exemple dans `.env.example` :

- `NUXT_PUBLIC_API_BASE` : URL API distante (prod ou local)
- `NUXT_PUBLIC_GITHUB_REPO` : slug `owner/repo` pour la page Download
- `NUXT_PUBLIC_DESKTOP_RELEASE_CHANNEL` : `latest` ou tag GitHub Release
- `NUXT_PUBLIC_GITHUB_API_BASE` : API GitHub (défaut `https://api.github.com`)

## Développement web

```bash
npm run dev
```

## Build web

```bash
npm run build
```

## Version desktop (Tauri)

### Dev desktop

```bash
npm run tauri:dev
```

Si vous voyez une erreur Cargo du type :

`this version of Cargo is older than the 2024 edition`

mettez à jour Rust/Cargo (Windows/macOS/Linux) :

```bash
rustup self update
rustup update stable
rustup default stable
```

Puis redémarrez le terminal et vérifiez :

```bash
cargo -V
rustc -V
```

Sous Windows, si la version ne change pas, vérifiez que `cargo` pointe bien vers `~/.cargo/bin` :

```bash
where cargo
where rustc
```

### Build desktop

```bash
npm run tauri:build
```

La commande génère d’abord le frontend Nuxt en mode desktop (`NUXT_DESKTOP_BUILD=1`) puis bundle l’application via Tauri.

## Comportement Vinted

- **Web** : fonctionnalités de mise en ligne Vinted désactivées, avec message d’orientation vers la page de téléchargement.
- **Desktop** : fonctionnalités Vinted disponibles (runtime détecté via Tauri WebView).

## CI/CD

- `deploy-web.yml` : build + déploiement web (Nitro + PM2).
- `desktop-release.yml` : build desktop Windows/macOS en **release** (binaire sans console Windows) et publication sur GitHub Release stable (`desktop`, non-prerelease).
