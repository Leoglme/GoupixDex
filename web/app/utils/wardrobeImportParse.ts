/**
 * Parse Vinted import title/description → GoupixDex form fields.
 */

const FORM_SUFFIX_RE = /^(?:ex|v|vmax|vstar|gx|tag\s*team|tt|break|lv\.?\s*x|lvx|mega)(?:\s|$)/i

/**
 *
 * @param longerCf
 * @param shorterCf
 */
function longerIsShorterPlusForm(longerCf: string, shorterCf: string): boolean {
  if (!longerCf.startsWith(shorterCf)) {
    return false
  }
  const rest = longerCf.slice(shorterCf.length).trim()
  if (!rest) {
    return true
  }
  return FORM_SUFFIX_RE.test(rest)
}

/**
 * Aligned with ``api/services/scan_service._fr_en_same_for_title`` (redundant titles / names).
 * @param nameFr
 * @param nameEn
 */
export function frEnSameForDisplay(nameFr: string, nameEn: string): boolean {
  const a = nameFr.trim()
  const b = nameEn.trim()
  if (!a || !b) {
    return false
  }
  if (a.toLowerCase() === b.toLowerCase()) {
    return true
  }
  const aCf = a.toLowerCase()
  const bCf = b.toLowerCase()
  if (longerIsShorterPlusForm(bCf, aCf) || longerIsShorterPlusForm(aCf, bCf)) {
    return true
  }
  return false
}

/**
 * Strip trailing `` ex`` / `` V`` etc. from English labels for the Pokémon name field.
 * @param s
 */
export function stripTrailingTcgFormSuffix(s: string): string {
  const t = s.trim()
  const re = /\s+(?:ex|v|vmax|vstar|gx)(?:\s|$)/i
  let out = t
  let prev = ''
  while (out !== prev) {
    prev = out
    out = out.replace(re, ' ').trim()
  }
  return out || t
}

/**
 * Name field: ``Fr / En`` → single label if redundant, else **French part** (before the slash).
 * @param raw
 */
export function normalizePokemonNameField(raw: string): string {
  const t = raw.trim()
  if (!t) {
    return ''
  }
  const slash = t.split(/\s*\/\s*/)
  if (slash.length >= 2) {
    const a = slash[0]!.trim()
    const b = slash.slice(1).join('/').trim()
    if (frEnSameForDisplay(a, b)) {
      return a
    }
    return a
  }
  return stripTrailingTcgFormSuffix(t)
}

/**
 * ``160/086 SR Super Rare`` → ``160/086``
 * @param raw
 */
export function parseFractionFromNumeroLine(raw: string): string {
  const m = raw.match(/(\d{1,4}\s*\/\s*\d{1,4})/)
  return m?.[1]?.replace(/\s*\/\s*/, '/') ?? raw.trim()
}

/**
 * Tokens like ``sv11w``, ``sv7``, ``m1l`` (contain a digit) — not an expansion name such as « White Flare ».
 * @param s
 */
function looksLikeSetCodeToken(s: string): boolean {
  const t = s.trim()
  if (!t || /\s/.test(t) || t.includes('/')) {
    return false
  }
  return /\d/.test(t)
}

export interface ParsedGoupixTitleHead {
  namePart: string
  setCode: string
  cardNumber: string
  variant?: string
}

/**
 * First segment of a GoupixDex-style title: ``{names} {code} {fraction} [variant] - …``.
 * @param title
 */
export function parseGoupixStyleTitleHead(title: string): ParsedGoupixTitleHead | null {
  const head = title.split(/\s*-\s*/)[0]?.trim() ?? ''
  if (!head) {
    return null
  }
  const fracM = head.match(/(\d{1,4}\s*\/\s*\d{1,4})/)
  if (!fracM || fracM.index == null) {
    return null
  }
  const cardNumber = fracM[1]!.replace(/\s*\/\s*/, '/')
  const before = head.slice(0, fracM.index).trimEnd()
  const after = head.slice(fracM.index + fracM[0]!.length).trim()
  let variant: string | undefined
  if (after && /^[A-Za-z]{1,12}$/.test(after)) {
    variant = after
  }
  const end = before.match(/^(.+)\s+(\S+)$/)
  if (!end) {
    return null
  }
  const setCode = end[2]!.trim()
  if (!looksLikeSetCodeToken(setCode)) {
    return null
  }
  const namePart = end[1]!.trim()
  return { namePart, setCode, cardNumber, variant }
}

/**
 *
 * @param serie
 */
function serieLooksLikeExpansionName(serie: string): boolean {
  const t = serie.trim()
  if (!t) {
    return true
  }
  if (/\s{2,}/.test(t)) {
    return true
  }
  const words = t.split(/\s+/)
  if (words.length >= 2 && !/\d/.test(t)) {
    return true
  }
  return false
}

/**
 *
 * @param title
 * @param serieLine
 */
export function pickSetCodeForForm(title: string, serieLine: string): string {
  const parsed = parseGoupixStyleTitleHead(title)
  if (parsed?.setCode) {
    return parsed.setCode
  }
  const s = serieLine.trim()
  if (s && !serieLooksLikeExpansionName(s) && looksLikeSetCodeToken(s)) {
    return s
  }
  return ''
}

/**
 *
 * @param title
 * @param numeroLine
 */
export function pickCardNumberForForm(title: string, numeroLine: string): string {
  const parsed = parseGoupixStyleTitleHead(title)
  if (parsed?.cardNumber) {
    return parsed.cardNumber
  }
  return parseFractionFromNumeroLine(numeroLine)
}

/**
 *
 * @param title
 * @param nomLine
 */
export function pickPokemonNameForForm(title: string, nomLine: string): string {
  const parsed = parseGoupixStyleTitleHead(title)
  const fromDesc = nomLine.trim()
  const raw = fromDesc || parsed?.namePart || ''
  return normalizePokemonNameField(raw)
}

const BOILERPLATE_HINTS = ['une communauté', 'milliers de marques', 'prêt à te lancer', 'découvre comment ça marche']

/**
 *
 * @param text
 */
export function isVintedMarketingDescription(text: string): boolean {
  const lower = text.toLowerCase()
  return BOILERPLATE_HINTS.some((h) => lower.includes(h))
}
