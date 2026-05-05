/**
 * Turns an ISO 3166-1 alpha-2 code into a regional-indicator flag emoji.
 * @param countryCode - Two-letter country code or empty.
 * @returns Flag emoji, or a globe fallback when invalid.
 */
export function flagEmoji(countryCode: string | null | undefined): string {
  const cc = (countryCode ?? '').trim().toUpperCase()
  if (cc.length !== 2 || !/^[A-Z]{2}$/.test(cc)) {
    return '🌍'
  }
  const base = 0x1f1e6
  const a = 'A'.charCodeAt(0)
  const chars = [...cc].map((ch) => base + (ch.charCodeAt(0) - a))
  return String.fromCodePoint(...chars)
}

/**
 * Sharp flag image URL (high-res source, scaled down in CSS for crisp display).
 * @param countryCode - Two-letter country code or empty.
 * @returns HTTPS URL for flagcdn.com asset, or null when invalid.
 */
export function countryFlagImgUrl(countryCode: string | null | undefined): string | null {
  const cc = (countryCode ?? '').trim().toUpperCase()
  if (cc.length !== 2 || !/^[A-Z]{2}$/.test(cc)) {
    return null
  }
  return `https://flagcdn.com/w80/${cc.toLowerCase()}.png`
}
