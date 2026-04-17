# eBay — configuration OAuth et mise en ligne (GoupixDex)

Ce document décrit comment préparer un compte [eBay Developers Program](https://developer.ebay.com/), configurer l’écran **Your eBay Sign-in Settings** (RuName / URLs de redirection), renseigner les variables d’environnement de l’API GoupixDex, puis connecter un vendeur depuis l’interface **Paramètres → Places de marché**.

## 1. Compte développeur et clés

1. Créez un compte sur [developer.ebay.com](https://developer.ebay.com/) et une **Application Keyset** (sandbox pour les tests, production quand vous êtes prêt).
2. Notez l’**App ID (Client ID)** et le **Cert ID (Client Secret)** — ce ne sont pas les jetons d’accès API ; ils servent uniquement à l’échange OAuth côté serveur.

## 2. « Your eBay Sign-in Settings » (RuName)

Dans le portail développeur, configurez la page OAuth :

| Champ | Rôle |
|--------|------|
| **Display Title** | Nom affiché sur la page de consentement (ex. `GoupixDex`). |
| **Your privacy policy URL** | URL accessible d’une politique de confidentialité (exigence programme développeur). |
| **Your auth accepted URL** | **URL de callback OAuth** : eBay y redirige avec `?code=...&state=...` après accord. Elle doit être **identique** à la valeur `EBAY_REDIRECT_URI` / à l’URL utilisée dans l’app. Exemple : `https://votre-domaine.fr/settings/marketplaces` ou en local `http://localhost:3000/settings/marketplaces` (sandbox accepte souvent l’HTTP en dev). |
| **Your auth declined URL** | Page si l’utilisateur refuse (ex. retour dashboard ou message simple). |

**Important :** pas de différence de slash final, de `http` vs `https`, ou de host (`localhost` vs `127.0.0.1`) entre le portail eBay, `EBAY_REDIRECT_URI` et l’URL réellement ouverte dans le navigateur.

## 3. Scopes utilisés par GoupixDex

L’API demande les scopes suivants (déjà codés côté backend) :

- `https://api.ebay.com/oauth/api_scope/sell.inventory` — création d’annonces (Inventory API).
- `https://api.ebay.com/oauth/api_scope/sell.account` — lecture des politiques d’expédition, paiement et retours.

## 4. Variables d’environnement (API)

Ajoutez dans `api/.env` (voir `api/.env.example`) :

| Variable | Description |
|----------|-------------|
| `EBAY_CLIENT_ID` | App ID (Client ID) — **sandbox ou prod** selon `EBAY_USE_SANDBOX`. |
| `EBAY_CLIENT_SECRET` | Cert ID (Client Secret). |
| `EBAY_REDIRECT_URI` | **Exactement** la même URL que *Your auth accepted URL* (ex. `https://.../settings/marketplaces`). |
| `EBAY_USE_SANDBOX` | `true` pour `auth.sandbox.ebay.com` / `api.sandbox.ebay.com`, `false` pour la production. |
| `EBAY_DEFAULT_CATEGORY_ID` | *(Optionnel)* ID de catégorie feuille pour le marketplace ciblé. Si renseigné, les utilisateurs peuvent laisser la catégorie vide dans l’app ; la valeur utilisateur reste prioritaire. |

Redémarrez l’API après modification.

## 5. Flux dans l’application web

1. **Paramètres → Marketplace** : activez **eBay**, enregistrez si besoin.
2. Cliquez **Se connecter à eBay** : redirection vers la page de consentement eBay.
3. Après acceptation, eBay renvoie vers `/settings/marketplaces?code=...&state=...` : le front envoie le `code` au backend (`POST /ebay/oauth/exchange`), qui stocke les jetons (chiffrés) sur l’utilisateur.
4. Choisissez **l’emplacement d’expédition** et les **trois politiques** (expédition, paiement, retours) dans les listes proposées après connexion (données lues sur votre compte eBay). Si une liste est vide, créez d’abord l’emplacement / les politiques dans l’espace vendeur eBay.
5. **Catégorie** : soit renseignée par l’administrateur dans `EBAY_DEFAULT_CATEGORY_ID`, soit saisie (override) dans l’interface. Sans catégorie effective (ni défaut ni champ utilisateur), la publication reste bloquée.

Sans emplacement ni politiques, la publication est ignorée avec un message explicite.

## 6. Images et sandbox

- Les images d’annonce doivent être en **HTTPS** (ex. URLs Supabase) — exigence eBay Inventory API.
- En **sandbox**, utilisez des comptes / annonces de test ; les IDs de catégories et politiques doivent exister pour le marketplace choisi (ex. `EBAY_FR`).

## 7. Références officielles

- [Authorization code grant](https://developer.ebay.com/api-docs/static/oauth-authorization-code-grant.html)
- [Getting user consent](https://developer.ebay.com/api-docs/static/oauth-consent-request.html)
- [Exchanging the authorization code](https://developer.ebay.com/api-docs/static/oauth-auth-code-grant-request.html)
- [Inventory API — createOrReplaceInventoryItem](https://developer.ebay.com/api-docs/sell/inventory/resources/inventory_item/methods/createOrReplaceInventoryItem)
- [createOffer / publishOffer](https://developer.ebay.com/api-docs/sell/inventory/resources/offer/methods/createOffer)

## 8. Dépannage rapide

- **Erreur à l’échange de code** : `redirect_uri` différent de celui enregistré chez eBay, ou `code` déjà consommé / expiré (les codes sont à usage unique et très courts).
- **Erreur à la publication** : catégorie incorrecte, politiques incompatibles avec le marketplace, ou **descripteurs d’état** obligatoires pour certaines catégories cartes — consultez les messages d’erreur dans les logs API (`ebay_body`).
