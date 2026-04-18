# eBay — OAuth setup and publishing (GoupixDex)

This document explains how to prepare an [eBay Developers Program](https://developer.ebay.com/) account, configure **Your eBay Sign-in Settings** (RuName / redirect URLs), set GoupixDex API environment variables, and connect a seller from **Settings → Marketplaces**.

## 1. Developer account and keys

1. Create an account on [developer.ebay.com](https://developer.ebay.com/) and an **Application Keyset** (sandbox for tests, production when ready).
2. Note the **App ID (Client ID)** and **Cert ID (Client Secret)** — these are not API access tokens; they are only used for OAuth on the server.

## 2. “Your eBay Sign-in Settings” (RuName)

In the developer portal, configure OAuth:

| Field | Role |
|--------|------|
| **Display Title** | Name shown on the consent page (e.g. `GoupixDex`). |
| **Your privacy policy URL** | URL of a privacy policy (developer program requirement). |
| **Your auth accepted URL** | **OAuth callback URL**: eBay redirects here with `?code=...&state=...` after approval. It must **match** `EBAY_REDIRECT_URI` / the URL opened in the app. Example: `https://your-domain.fr/settings/marketplaces` or locally `http://localhost:3000/settings/marketplaces` (sandbox often allows HTTP in dev). |
| **Your auth declined URL** | Page if the user declines (e.g. return to dashboard). |

**Important:** no mismatch in trailing slash, `http` vs `https`, or host (`localhost` vs `127.0.0.1`) between the eBay portal, `EBAY_REDIRECT_URI`, and the URL actually opened in the browser.

## 3. Scopes used by GoupixDex

The API requests these scopes (already set in the backend):

- `https://api.ebay.com/oauth/api_scope/sell.inventory` — listings (Inventory API).
- `https://api.ebay.com/oauth/api_scope/sell.account` — fulfillment, payment, and return policies.

## 4. Environment variables (API)

Add to `api/.env` (see `api/.env.example`):

| Variable | Description |
|----------|-------------|
| `EBAY_CLIENT_ID` | App ID (Client ID) — **sandbox or prod** depending on `EBAY_USE_SANDBOX`. |
| `EBAY_CLIENT_SECRET` | Cert ID (Client Secret). |
| `EBAY_REDIRECT_URI` | **Exactly** the same URL as *Your auth accepted URL* (e.g. `https://.../settings/marketplaces`). |
| `EBAY_USE_SANDBOX` | `true` for `auth.sandbox.ebay.com` / `api.sandbox.ebay.com`, `false` for production. |

Restart the API after changes.

Fulfillment shipping options (multiple domestic rates, international, handling time) are created or updated via the Account API when you run onboarding or `POST /ebay/policies/fulfillment/ensure` — no manual policy setup on ebay.fr is required in the default flow.

## 5. Flow in the web app

1. **Settings → Marketplace**: enable **eBay**, save if needed.
2. Click **Connect to eBay**: redirect to eBay consent.
3. After approval, eBay redirects to `/settings/marketplaces?code=...&state=...`: the frontend sends `code` to the backend (`POST /ebay/oauth/exchange`), which stores encrypted tokens on the user row.
4. **Onboarding**: after connection, enter the **ship-from address** and call `POST /ebay/onboarding/setup`, which opts into business policies if needed, creates a default **inventory location** and **policies** for eBay France when missing, and saves IDs in GoupixDex.
5. **Category**: the default leaf category for listings (single JCC / Pokémon cards on **eBay France**) is defined in code (`EBAY_FR_DEFAULT_LEAF_CATEGORY_ID` in `api/config.py`). A different value can still be stored per user in `ebay_category_id` if needed.

## 6. Images and sandbox

- Listing images must be **HTTPS** (e.g. Supabase URLs) — required by the eBay Inventory API.
- In **sandbox**, use test accounts and listings; category and policy IDs must exist for the chosen marketplace (e.g. `EBAY_FR`).

## 7. Official references

- [Authorization code grant](https://developer.ebay.com/api-docs/static/oauth-authorization-code-grant.html)
- [Getting user consent](https://developer.ebay.com/api-docs/static/oauth-consent-request.html)
- [Exchanging the authorization code](https://developer.ebay.com/api-docs/static/oauth-auth-code-grant-request.html)
- [Inventory API — createOrReplaceInventoryItem](https://developer.ebay.com/api-docs/sell/inventory/resources/inventory_item/methods/createOrReplaceInventoryItem)
- [createOffer / publishOffer](https://developer.ebay.com/api-docs/sell/inventory/resources/offer/methods/createOffer)

## 8. Quick troubleshooting

- **Token exchange error**: `redirect_uri` does not match what is registered at eBay, or `code` already used / expired (codes are single-use and short-lived).
- **“User is not eligible for Business Policy”** (logs: error 20403 on `fulfillment_policy`): the account must be enrolled in **business policies**. The API calls [`optInToProgram`](https://developer.ebay.com/api-docs/sell/account/resources/program/methods/optInToProgram) with `SELLING_POLICY_MANAGEMENT` before loading policies; eBay can take **up to ~24 h** to activate — retry later or check with `getOptedInPrograms`.
- **Publishing error**: wrong category, policies incompatible with the marketplace, or **condition descriptors** required for some card categories — see API logs (`ebay_body`).
