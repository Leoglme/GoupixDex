/**
 * Préremplissage création groupée à partir du document renvoyé par le worker
 * ``POST /vinted/wardrobe-sync/jobs`` (champ ``result``).
 */

import {
  isVintedMarketingDescription,
  pickCardNumberForForm,
  pickPokemonNameForForm,
  pickSetCodeForForm
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
  /** Annonce déjà présente sur Vinted (import garde-robe) — à refléter en base. */
  wardrobeVintedListed: boolean
  /** Date de mise en ligne côté Vinted (ISO), annonces actives. */
  vintedPublishedAtIso: string | null
  /** Prix encaissé / alloué pour une vente importée (champ sold_price). */
  importSoldPrice: string | null
}

const VINTED_STATUS_TO_CONDITION: Record<string, string> = {
  'Neuf avec étiquette': 'Mint',
  'Neuf sans étiquette': 'Near Mint',
  'Très bon état': 'Excellent',
  'Bon état': 'Good',
  Satisfaisant: 'Played'
}

function lineValue(desc: string, label: string): string {
  const re = new RegExp(
    `^\\s*${label}\\s*:\\s*(.+)\\s*$`,
    'im'
  )
  const m = desc.match(re)
  return m?.[1]?.trim() ?? ''
}

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

function mapVintedCondition(status: unknown, description: string): string {
  const fromDesc = parseEtatFromDescription(description)
  if (fromDesc) {
    return fromDesc
  }
  const key = typeof status === 'string' ? status.trim() : ''
  return VINTED_STATUS_TO_CONDITION[key] ?? 'Near Mint'
}

function normalizeSoldAt(raw: string): string {
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) {
    return new Date().toISOString()
  }
  return d.toISOString()
}

function rowPriceAmount(row: Record<string, unknown>): string {
  const price = row.price as { amount?: unknown } | undefined
  if (price?.amount == null) {
    return ''
  }
  return String(price.amount).replace(',', '.').trim()
}

/** Prix réalisé côté vendeur pour une ligne vendue (allocation transaction). */
function rowSoldProceedsAmount(row: Record<string, unknown>): string | null {
  const total = row.total_item_price as { amount?: unknown } | undefined
  if (total?.amount != null && String(total.amount).trim()) {
    return String(total.amount).replace(',', '.').trim()
  }
  const p = rowPriceAmount(row)
  return p || null
}

function rowPhotoUrls(row: Record<string, unknown>): string[] {
  const urls = row.photo_urls
  if (!Array.isArray(urls)) {
    return []
  }
  return urls.filter((u): u is string => typeof u === 'string' && u.startsWith('http'))
}

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
  const listedUtc
    = typeof row.listed_at_utc === 'string' && row.listed_at_utc.trim()
      ? row.listed_at_utc.trim()
      : null
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
    importSoldPrice: importSold
  }
}

export function syncResultToPrefillSlots(result: Record<string, unknown>): WardrobeSlotPrefill[] {
  const active = Array.isArray(result.active_items)
    ? (result.active_items as Record<string, unknown>[])
    : []
  const sold = Array.isArray(result.sold_items)
    ? (result.sold_items as Record<string, unknown>[])
    : []
  return [...active, ...sold].map(rowToSlot)
}
