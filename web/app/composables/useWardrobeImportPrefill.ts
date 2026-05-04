/**
 * Batch-create prefill from the document returned by the worker
 * ``POST /vinted/wardrobe-sync/jobs`` (``result`` field).
 */

import {
  isVintedMarketingDescription,
  pickCardNumberForForm,
  pickPokemonNameForForm,
  pickSetCodeForForm,
} from '~/utils/wardrobeImportParse'

export const WARDROBE_IMPORT_STORAGE_KEY = 'goupix_wardrobe_import'

export interface WardrobeSlotPrefill {
  title: string
  description: string
  sellPrice: string
  purchasePrice: string
  condition: string
  pokemonName: string
  setCode: string
  cardNumber: string
  photoUrls: string[]
  isSold: boolean
  soldAt: string | null
  /** Listing already on Vinted (wardrobe import) — mirror in DB. */
  wardrobeVintedListed: boolean
  /** Vinted go-live date (ISO) for active listings. */
  vintedPublishedAtIso: string | null
  /** Proceeds / allocated amount for an imported sale (sold_price field). */
  importSoldPrice: string | null
}

const VINTED_STATUS_TO_CONDITION: Record<string, string> = {
  'Neuf avec étiquette': 'Mint',
  'Neuf sans étiquette': 'Near Mint',
  'Très bon état': 'Excellent',
  'Bon état': 'Good',
  Satisfaisant: 'Played',
}

/**
 * Read a single `Label: value` line from a free-text description block.
 *
 * @param desc - Full listing description text.
 * @param label - Line prefix to match (case-sensitive French labels).
 * @returns {string} Trimmed value after the colon, or empty string.
 */
function lineValue(desc: string, label: string): string {
  const re = new RegExp(`^\\s*${label}\\s*:\\s*(.+)\\s*$`, 'im')
  const m = desc.match(re)
  return m?.[1]?.trim() ?? ''
}

/**
 * Infer English TCG-style condition tokens from the `État:` line when present.
 *
 * @param desc - Listing description containing optional structured lines.
 * @returns {string} Mapped condition (`Mint`, `Near Mint`, …) or empty string.
 */
function parseEtatFromDescription(desc: string): string {
  const raw = lineValue(desc, 'État')
  if (!raw) {
    return ''
  }
  const lower = raw.toLowerCase()
  if (lower.includes('played') || lower.includes('heavily')) {
    return 'Played'
  }
  if (lower.includes('good') && !lower.includes('near')) {
    return 'Good'
  }
  if (lower.includes('excellent') || lower.includes('très bon')) {
    return 'Excellent'
  }
  if (lower.includes('mint') && !lower.includes('near')) {
    return 'Mint'
  }
  if (lower.includes('near') || lower.includes('nm')) {
    return 'Near Mint'
  }
  return ''
}

/**
 * Map Vinted wardrobe status + description text to our article `condition` field.
 *
 * @param status - Raw `status` string from the wardrobe API row.
 * @param description - Full description for regex-based `État` fallback.
 * @returns {string} Condition label stored on the article form.
 */
function mapVintedCondition(status: unknown, description: string): string {
  const fromDesc = parseEtatFromDescription(description)
  if (fromDesc) {
    return fromDesc
  }
  const key = typeof status === 'string' ? status.trim() : ''
  return VINTED_STATUS_TO_CONDITION[key] ?? 'Near Mint'
}

/**
 * Normalize a sold timestamp string to ISO (fallback: now).
 *
 * @param raw - Worker-provided datetime string.
 * @returns {string} ISO 8601 string.
 */
function normalizeSoldAt(raw: string): string {
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) {
    return new Date().toISOString()
  }
  return d.toISOString()
}

/**
 * Listed asking price from `row.price.amount` (comma-normalized).
 *
 * @param row - Wardrobe item row from the worker JSON.
 * @returns {string} Decimal string for form inputs, or empty when missing.
 */
function rowPriceAmount(row: Record<string, unknown>): string {
  const price = row.price as { amount?: unknown } | undefined
  if (price?.amount == null) {
    return ''
  }
  return String(price.amount).replace(',', '.').trim()
}

/**
 * Seller-side realized price for a sold row (transaction allocation).
 *
 * @param row - Wardrobe item row (sold branch).
 * @returns {string | null} Proceeds as decimal string, or display price fallback.
 */
function rowSoldProceedsAmount(row: Record<string, unknown>): string | null {
  const total = row.total_item_price as { amount?: unknown } | undefined
  if (total?.amount != null && String(total.amount).trim()) {
    return String(total.amount).replace(',', '.').trim()
  }
  const p = rowPriceAmount(row)
  return p || null
}

/**
 * Collect HTTP(S) photo URLs attached to the wardrobe row.
 *
 * @param row - Wardrobe item row.
 * @returns {string[]} Absolute URLs suitable for download via the local worker.
 */
function rowPhotoUrls(row: Record<string, unknown>): string[] {
  const urls = row.photo_urls
  if (!Array.isArray(urls)) {
    return []
  }
  return urls.filter((u): u is string => typeof u === 'string' && u.startsWith('http'))
}

/**
 * Convert one wardrobe JSON row into a batch-create slot prefill object.
 *
 * @param row - Raw object from `active_items` / `sold_items`.
 * @returns {WardrobeSlotPrefill} Normalized slot for `ArticleForm` defaults.
 */
function rowToSlot(row: Record<string, unknown>): WardrobeSlotPrefill {
  let desc = String(row.description ?? '').trim()
  const title = String(row.title ?? '').trim()
  if (isVintedMarketingDescription(desc)) {
    desc = ''
  }
  const nomLine = lineValue(desc, 'Nom')
  const serieLine = lineValue(desc, 'Série')
  const numeroLine = lineValue(desc, 'Numéro')
  const isSold = row.is_sold === true
  let soldAt: string | null = null
  if (isSold && row.transaction_debit_processed_at) {
    soldAt = normalizeSoldAt(String(row.transaction_debit_processed_at))
  }
  const listedUtc = typeof row.listed_at_utc === 'string' && row.listed_at_utc.trim() ? row.listed_at_utc.trim() : null
  const importSold = isSold ? rowSoldProceedsAmount(row) : null
  return {
    title: title || 'Annonce Vinted',
    description: desc || title,
    sellPrice: rowPriceAmount(row),
    purchasePrice: '0',
    condition: mapVintedCondition(row.status, desc),
    pokemonName: pickPokemonNameForForm(title, nomLine),
    setCode: pickSetCodeForForm(title, serieLine),
    cardNumber: pickCardNumberForForm(title, numeroLine),
    photoUrls: rowPhotoUrls(row),
    isSold,
    soldAt,
    wardrobeVintedListed: true,
    vintedPublishedAtIso: !isSold ? listedUtc : null,
    importSoldPrice: importSold,
  }
}

/**
 * Flatten `active_items` + `sold_items` from a wardrobe sync `result` payload into form slots.
 *
 * @param result - `result` object returned when the sync job completes.
 * @returns {WardrobeSlotPrefill[]} Ordered slots for multi-row batch create UI.
 */
export function syncResultToPrefillSlots(result: Record<string, unknown>): WardrobeSlotPrefill[] {
  const active = Array.isArray(result.active_items) ? (result.active_items as Record<string, unknown>[]) : []
  const sold = Array.isArray(result.sold_items) ? (result.sold_items as Record<string, unknown>[]) : []
  return [...active, ...sold].map(rowToSlot)
}
