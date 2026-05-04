/**
 * Amazon Invites page UI preferences (localStorage, client only).
 */

import type { AmazonStatusFilter } from '~/types/amazonInvites'

const KEY = 'goupix_amazon_invites_prefs'

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
    const next = { ...prev, ...prefs } as Record<string, unknown>
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* storage quota / private mode */
  }
}
