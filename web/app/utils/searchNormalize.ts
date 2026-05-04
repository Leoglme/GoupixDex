/**
 * Normalize a search query (case-insensitive, strip accents, collapse spaces).
 * @param raw
 */
export function normalizeSearchQuery(raw: string): string {
  return raw.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().replace(/\s+/g, ' ').trim()
}
