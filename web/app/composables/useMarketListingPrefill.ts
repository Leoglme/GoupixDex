import type { MarketListing } from '~/composables/useMarketSearch'

const EXCLUDED_TOKENS = new Set([
  'NEW',
  'SEALED',
  'SCELLE',
  'SCELLÉ',
  'MINT',
  'NM',
  'EX',
  'EXCELLENT',
  'FR',
  'FRENCH',
  'FRANCAIS',
  'FRANÇAIS',
  'FRANCE',
  'ENGLISH',
  'ENG',
  'JP',
  'JAPAN',
  'JAPONAIS',
  'POKEMON',
  'POKÉMON',
  'PSA',
  'CGC',
  'BGS',
  'BECKETT',
  'GRADED',
  'VMAX',
  'VSTAR',
  'V',
  'GX',
  'EX',
  'TAG',
  'TEAM',
])

export function mapMarketCondition(ebayCondition: string, isGraded: boolean): string {
  if (isGraded) {
    return 'Mint'
  }
  const c = (ebayCondition || '').toLowerCase()
  if (c.includes('new') || c.includes('neuf') || c.includes('scellé') || c.includes('scelle')) {
    return 'Mint'
  }
  if (c.includes('like new') || c.includes('comme neuf')) {
    return 'Near Mint'
  }
  if (c.includes('excellent') || c.includes('très bon')) {
    return 'Excellent'
  }
  if (c.includes('good') || c.includes('bon')) {
    return 'Good'
  }
  if (c.includes('played') || c.includes('acceptable')) {
    return 'Played'
  }
  return 'Near Mint'
}

export function buildMarketListingDescription(listing: MarketListing): string {
  const lines: string[] = [listing.title]
  if (listing.condition) {
    lines.push('', `État eBay : ${listing.condition}`)
  }
  if (listing.graded) {
    lines.push(`Gradée ${listing.graded.grader}${listing.graded.grade ? ` ${listing.graded.grade}` : ''}`)
  }
  return lines.join('\n').trim()
}

export function parseCardInfoFromTitle(title: string): {
  pokemonName: string
  setCode: string
  cardNumber: string
} {
  const result = { pokemonName: '', setCode: '', cardNumber: '' }
  const numberMatch = title.match(/\b(\d{1,3})\s*\/\s*(\d{1,3})\b/)
  if (numberMatch) {
    result.cardNumber = numberMatch[1]!
  }
  const setMatch = title.match(
    /\b(SWSH\d{1,3}[a-z]?|SV\d{1,3}[a-z]?|SM\d{1,3}[a-z]?|BW\d{1,3}[a-z]?|XY\d{1,3}[a-z]?|EB\d{1,3}[a-z]?|EV\d{1,3}[a-z]?|BKS?\d{1,3}[a-z]?)\b/i,
  )
  if (setMatch) {
    result.setCode = setMatch[1]!.toUpperCase()
  }
  const cleaned = title.replace(/[^\p{L}\p{N}\s-]+/gu, ' ')
  const tokens = cleaned.split(/\s+/).filter(Boolean)
  for (const tok of tokens) {
    const upper = tok.toUpperCase()
    if (EXCLUDED_TOKENS.has(upper)) {
      continue
    }
    if (/^\d+$/.test(tok)) {
      continue
    }
    if (tok.length < 3) {
      continue
    }
    if (/^[A-ZÀ-ÖØ-Ý]/u.test(tok[0] ?? '')) {
      result.pokemonName = tok
      break
    }
  }
  return result
}

export function buildArticlePrefillFromListing(listing: MarketListing): Record<string, string> {
  const payload: Record<string, string> = {
    title: listing.title,
    purchase_price: String(listing.price_eur),
    condition: mapMarketCondition(listing.condition, !!listing.graded),
  }
  const description = buildMarketListingDescription(listing)
  if (description) {
    payload.description = description
  }
  const parsed = parseCardInfoFromTitle(listing.title)
  if (parsed.pokemonName) {
    payload.pokemon_name = parsed.pokemonName
  }
  if (parsed.setCode) {
    payload.set_code = parsed.setCode
  }
  if (parsed.cardNumber) {
    payload.card_number = parsed.cardNumber
  }
  if (listing.image_url) {
    payload.image_url = listing.image_url
  }
  payload.source_url = listing.listing_url
  return payload
}
