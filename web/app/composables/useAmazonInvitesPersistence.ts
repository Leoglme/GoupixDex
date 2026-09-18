/**
 * Amazon Invites page UI preferences (localStorage, client only).
 */

import type { AmazonInvite, AmazonStatusFilter } from '~/types/amazonInvites'

const KEY = 'goupix_amazon_invites_prefs'

/** Maximum number of invite rows kept in the localStorage cache. */
const CACHED_INVITES_LIMIT = 300

export interface AmazonInvitesUiPrefs {
  /** Local filter on the list already loaded */
  searchQuery: string
  hideExpired: boolean
  /** Optional search sent to the worker (fetch) */
  optionalSearch: string
  /** Number of Amazon result pages to scan */
  maxPages: number
  /** Filter rows by invitation status */
  statusFilter?: AmazonStatusFilter
  /** Last fetched invite rows, shown immediately when reopening the page. */
  cachedInvites?: AmazonInvite[]
  /** ISO timestamp of the last successful fetch. */
  cachedRefreshedAt?: string | null
}

/**
 * Narrow an unknown value to a plausible {@link AmazonInvite} row.
 *
 * @param v - Raw value from storage.
 * @returns Whether `v` carries the minimal invite fields.
 */
function isPlausibleInvite(v: unknown): v is AmazonInvite {
  if (!v || typeof v !== 'object') {
    return false
  }
  const r = v as Record<string, unknown>
  return typeof r.id === 'string' && typeof r.title === 'string' && typeof r.status === 'string'
}

/**
 * Read persisted Amazon-invites UI prefs (SSR-safe).
 *
 * @returns {Partial<AmazonInvitesUiPrefs> | null} Parsed partial prefs, or `null`.
 */
export function loadAmazonInvitesPrefs(): Partial<AmazonInvitesUiPrefs> | null {
  if (!import.meta.client) {
    return null
  }
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) {
      return null
    }
    const p = JSON.parse(raw) as Record<string, unknown>
    const out: Partial<AmazonInvitesUiPrefs> = {}
    if (typeof p.searchQuery === 'string') {
      out.searchQuery = p.searchQuery
    }
    if (typeof p.hideExpired === 'boolean') {
      out.hideExpired = p.hideExpired
    }
    if (typeof p.optionalSearch === 'string') {
      out.optionalSearch = p.optionalSearch
    }
    if (typeof p.maxPages === 'number' && Number.isFinite(p.maxPages)) {
      out.maxPages = Math.min(50, Math.max(1, Math.round(p.maxPages)))
    }
    if (
      p.statusFilter === 'all' ||
      p.statusFilter === 'accepted' ||
      p.statusFilter === 'requested' ||
      p.statusFilter === 'not_requested'
    ) {
      out.statusFilter = p.statusFilter
    }
    if (Array.isArray(p.cachedInvites)) {
      out.cachedInvites = p.cachedInvites.filter(isPlausibleInvite).slice(0, CACHED_INVITES_LIMIT)
    }
    if (typeof p.cachedRefreshedAt === 'string') {
      out.cachedRefreshedAt = p.cachedRefreshedAt
    }
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}

/**
 * Merge prefs into `localStorage` (best-effort; ignores quota errors).
 *
 * @param prefs - Partial fields to merge onto the stored JSON object.
 * @returns {void} Nothing.
 */
export function saveAmazonInvitesPrefs(prefs: Partial<AmazonInvitesUiPrefs>): void {
  if (!import.meta.client) {
    return
  }
  try {
    const prevRaw = localStorage.getItem(KEY)
    const prev = prevRaw ? (JSON.parse(prevRaw) as Record<string, unknown>) : {}
    const capped: Partial<AmazonInvitesUiPrefs> = prefs.cachedInvites
      ? { ...prefs, cachedInvites: prefs.cachedInvites.slice(0, CACHED_INVITES_LIMIT) }
      : prefs
    const next = { ...prev, ...capped } as Record<string, unknown>
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* storage quota / private mode */
  }
}
