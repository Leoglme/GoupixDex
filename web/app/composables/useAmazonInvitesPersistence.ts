/**
 * Amazon Invites page UI preferences (localStorage, client only).
 */

import type { AmazonInvite, AmazonStatusFilter } from '~/types/amazonInvites'

const KEY = 'goupix_amazon_invites_prefs'

/** Maximum number of invite rows kept in the localStorage cache. */
const CACHED_INVITES_LIMIT = 300

/** Invite rows + timestamp cached for one vault account id. */
export interface AmazonInvitesAccountCache {
  items: AmazonInvite[]
  refreshedAt: string | null
}

export interface AmazonInvitesUiPrefs {
  /** Filtre local + requête worker à l’actualisation */
  searchQuery: string
  /** @deprecated fusionné dans searchQuery */
  optionalSearch?: string
  /** @deprecated retiré */
  hideExpired?: boolean
  /** Max invite rows to fetch on refresh (worker derives page depth). */
  maxItems: number
  /** @deprecated use maxItems */
  maxPages?: number
  /** Filter rows by invitation status */
  statusFilter?: AmazonStatusFilter
  /** Last fetched invite rows, shown immediately when reopening the page. */
  cachedInvites?: AmazonInvite[]
  /** ISO timestamp of the last successful fetch. */
  cachedRefreshedAt?: string | null
  /** Per vault account — instant UI when switching accounts. */
  invitesByAccount?: Record<string, AmazonInvitesAccountCache>
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
    if (typeof p.maxItems === 'number' && Number.isFinite(p.maxItems)) {
      out.maxItems = Math.min(500, Math.max(1, Math.round(p.maxItems)))
    } else if (typeof p.maxPages === 'number' && Number.isFinite(p.maxPages)) {
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

/**
 *
 */
function readInvitesByAccount(): Record<string, AmazonInvitesAccountCache> {
  const p = loadAmazonInvitesPrefs()
  const raw = p?.invitesByAccount
  if (!raw || typeof raw !== 'object') {
    return {}
  }
  const out: Record<string, AmazonInvitesAccountCache> = {}
  for (const [k, v] of Object.entries(raw)) {
    if (!v || typeof v !== 'object') {
      continue
    }
    const row = v as AmazonInvitesAccountCache
    if (!Array.isArray(row.items)) {
      continue
    }
    const items = row.items.filter(isPlausibleInvite).slice(0, CACHED_INVITES_LIMIT)
    if (!items.length) {
      continue
    }
    out[k] = {
      items,
      refreshedAt: typeof row.refreshedAt === 'string' ? row.refreshedAt : null,
    }
  }
  return out
}

/**
 * Persist invite rows for one vault account (statuses differ per Amazon login).
 */
export function saveInvitesCacheForAccount(accountId: number, items: AmazonInvite[], refreshedAt: string | null): void {
  if (!import.meta.client || !Number.isFinite(accountId)) {
    return
  }
  const key = String(accountId)
  const by = readInvitesByAccount()
  by[key] = {
    items: items.slice(0, CACHED_INVITES_LIMIT),
    refreshedAt,
  }
  saveAmazonInvitesPrefs({ invitesByAccount: by })
}

/**
 * Load cached invite rows for a vault account, if any.
 */
export function loadInvitesCacheForAccount(accountId: number): AmazonInvitesAccountCache | null {
  if (!import.meta.client || !Number.isFinite(accountId)) {
    return null
  }
  return readInvitesByAccount()[String(accountId)] ?? null
}
