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

/**
 * Extracts Cardmarket product URLs from a free-form text block.
 * Tolerant to mixed separators (newlines, tabs, spaces, commas, semicolons),
 * surrounding text, and trailing punctuation. Duplicates are removed while
 * preserving first-seen order.
 * @param text - Raw textarea content pasted by the user.
 * @returns Ordered list of unique HTTP(S) URLs.
 */
export function parseCardmarketUrlsFromText(text: string | null | undefined): string[] {
  if (!text) {
    return []
  }
  const matches = text.match(/https?:\/\/\S+/gi)
  if (!matches) {
    return []
  }
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of matches) {
    const cleaned = raw.replace(/[.,;:!?)\]}>'"`]+$/g, '').trim()
    if (!cleaned) {
      continue
    }
    if (seen.has(cleaned)) {
      continue
    }
    seen.add(cleaned)
    out.push(cleaned)
  }
  return out
}
