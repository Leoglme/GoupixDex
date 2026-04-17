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
| `EBAY_FR_FULFILLMENT_CARRIER_CODE` | *(Optionnel, défaut `Colissimo`)* Transporteur pour la politique d’expédition créée automatiquement. |
| `EBAY_FR_FULFILLMENT_SERVICE_CODE` | *(Optionnel, défaut `FR_ColiposteColissimo`)* Code service d’affranchissement ; à ajuster si eBay renvoie une erreur sur la création de politique. |

Redémarrez l’API après modification.

## 5. Flux dans l’application web

1. **Paramètres → Marketplace** : activez **eBay**, enregistrez si besoin.
2. Cliquez **Se connecter à eBay** : redirection vers la page de consentement eBay.
3. Après acceptation, eBay renvoie vers `/settings/marketplaces?code=...&state=...` : le front envoie le `code` au backend (`POST /ebay/oauth/exchange`), qui stocke les jetons (chiffrés) sur l’utilisateur.
4. **Assistant** : après connexion, l’app propose de saisir **l’adresse d’expédition** puis appelle `POST /ebay/onboarding/setup`, qui inscrit le compte aux politiques métier si besoin, crée un **emplacement inventaire** et des **politiques** par défaut (eBay France) lorsqu’ils manquent, et enregistre les IDs côté GoupixDex. Aucune configuration manuelle sur ebay.fr n’est nécessaire dans le flux normal.
5. **Catégorie** : l’ID de catégorie feuille pour les annonces (cartes JCC / Pokémon à l’unité sur **eBay France**) est défini dans le code (`EBAY_FR_DEFAULT_LEAF_CATEGORY_ID` dans `api/config.py`). Une valeur différente peut encore être enregistrée par utilisateur dans `ebay_category_id` si besoin.

Si la création automatique de la politique d’**expédition** échoue (service postal invalide), ajustez `EBAY_FR_FULFILLMENT_CARRIER_CODE` et `EBAY_FR_FULFILLMENT_SERVICE_CODE` (valeurs attendues par eBay pour `EBAY_FR`).

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
- **« User is not eligible for Business Policy »** (logs : erreur 20403 sur `fulfillment_policy`) : le compte doit être inscrit au programme **politiques métier**. L’API appelle automatiquement [`optInToProgram`](https://developer.ebay.com/api-docs/sell/account/resources/program/methods/optInToProgram) avec `SELLING_POLICY_MANAGEMENT` avant de charger les politiques ; eBay peut mettre **jusqu’à ~24 h** à activer — réessayez plus tard ou vérifiez avec `getOptedInPrograms`.
- **Erreur à la publication** : catégorie incorrecte, politiques incompatibles avec le marketplace, ou **descripteurs d’état** obligatoires pour certaines catégories cartes — consultez les messages d’erreur dans les logs API (`ebay_body`).
