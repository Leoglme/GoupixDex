/**
 * Cardmarket public URLs used in GoupixDex (French Pokémon section).
 */
const SELLER_PROFILE_BASE = 'https://www.cardmarket.com/fr/Pokemon/Users/'

/**
 * Builds the public seller profile URL on Cardmarket.
 * @param username - Seller login from PDF import (e.g. ``realkabe``).
 * @returns HTTPS URL, or null when username is empty.
 */
export function cardmarketSellerProfileUrl(username: string | null | undefined): string | null {
  const u = (username ?? '').trim()
  if (!u) {
    return null
  }
  return `${SELLER_PROFILE_BASE}${encodeURIComponent(u)}`
}
