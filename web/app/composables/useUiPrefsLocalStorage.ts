/**
 * Persistent UI preferences (localStorage), client-only.
 */

import type { DashboardRange } from '~/composables/useStats'

const ARTICLES_LIST_KEY = 'goupix_articles_list_prefs'
const DASHBOARD_KEY = 'goupix_dashboard_prefs'

/** @deprecated Legacy single-key sort — migrated to `sortColumn` + `sortDirection`. */
export type ArticleListSortKey = 'created_desc' | 'sold_desc' | 'purchase_asc' | 'purchase_desc'

export type ArticleListSortColumn =
  | 'name'
  | 'sold'
  | 'set'
  | 'number'
  | 'purchase'
  | 'sell'
  | 'realized'
  | 'created'
  | 'sold_at'

export type ArticleListSortDirection = 'asc' | 'desc'

export interface ArticleListPrefs {
  sortColumn: ArticleListSortColumn
  sortDirection: ArticleListSortDirection
  searchQuery: string
  /** Pagination size for article lists (default 10 if missing). */
  pageSize?: number
}

const SORT_COLUMNS: ArticleListSortColumn[] = [
  'name',
  'sold',
  'set',
  'number',
  'purchase',
  'sell',
  'realized',
  'created',
  'sold_at',
]

const SORT_KEYS: ArticleListSortKey[] = ['created_desc', 'sold_desc', 'purchase_asc', 'purchase_desc']

/**
 * Map legacy sort dropdown values to column + direction.
 */
export function articleListSortKeyToColumnDirection(key: ArticleListSortKey): {
  column: ArticleListSortColumn
  direction: ArticleListSortDirection
} {
  switch (key) {
    case 'sold_desc':
      return { column: 'sold_at', direction: 'desc' }
    case 'purchase_asc':
      return { column: 'purchase', direction: 'asc' }
    case 'purchase_desc':
      return { column: 'purchase', direction: 'desc' }
    case 'created_desc':
    default:
      return { column: 'created', direction: 'desc' }
  }
}
const PAGE_SIZES: number[] = [5, 10, 15, 30, 50, 100]

/**
 * Load persisted article-list UI preferences from `localStorage` (SSR-safe).
 *
 * @returns {Partial<ArticleListPrefs> | null} Parsed prefs, or `null` when absent or invalid.
 */
export function loadArticleListPrefs(): Partial<ArticleListPrefs> | null {
  if (!import.meta.client) {
    return null
  }
  try {
    const raw = localStorage.getItem(ARTICLES_LIST_KEY)
    if (!raw) {
      return null
    }
    const p = JSON.parse(raw) as Record<string, unknown>
    const out: Partial<ArticleListPrefs> = {}
    if (typeof p.sortColumn === 'string' && SORT_COLUMNS.includes(p.sortColumn as ArticleListSortColumn)) {
      out.sortColumn = p.sortColumn as ArticleListSortColumn
    }
    if (p.sortDirection === 'asc' || p.sortDirection === 'desc') {
      out.sortDirection = p.sortDirection
    }
    if (!out.sortColumn && typeof p.sortKey === 'string' && SORT_KEYS.includes(p.sortKey as ArticleListSortKey)) {
      const migrated = articleListSortKeyToColumnDirection(p.sortKey as ArticleListSortKey)
      out.sortColumn = migrated.column
      out.sortDirection = migrated.direction
    }
    if (typeof p.searchQuery === 'string') {
      out.searchQuery = p.searchQuery
    }
    if (typeof p.pageSize === 'number' && PAGE_SIZES.includes(p.pageSize)) {
      out.pageSize = p.pageSize
    }
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}

/**
 * Merge and persist article-list UI preferences to `localStorage`.
 *
 * @param prefs - Partial prefs to merge onto the stored JSON object.
 * @returns {void} Nothing.
 */
export function saveArticleListPrefs(prefs: Partial<ArticleListPrefs>): void {
  if (!import.meta.client) {
    return
  }
  try {
    const prevRaw = localStorage.getItem(ARTICLES_LIST_KEY)
    const prev = prevRaw ? (JSON.parse(prevRaw) as Record<string, unknown>) : {}
    const next = { ...prev, ...prefs } as Record<string, unknown>
    localStorage.setItem(ARTICLES_LIST_KEY, JSON.stringify(next))
  } catch {
    /* quota / private mode */
  }
}

export interface DashboardPrefsPersisted {
  range: { startIso: string; endIso: string }
}

/**
 * Load persisted dashboard date range / period / market-toggle prefs.
 *
 * @returns {Partial<DashboardPrefsPersisted> | null} Parsed prefs, or `null` when absent or invalid.
 */
export function loadDashboardPrefs(): Partial<DashboardPrefsPersisted> | null {
  if (!import.meta.client) {
    return null
  }
  try {
    const raw = localStorage.getItem(DASHBOARD_KEY)
    if (!raw) {
      return null
    }
    const p = JSON.parse(raw) as Record<string, unknown>
    const out: Partial<DashboardPrefsPersisted> = {}
    if (
      p.range &&
      typeof p.range === 'object' &&
      p.range !== null &&
      typeof (p.range as { startIso?: unknown }).startIso === 'string' &&
      typeof (p.range as { endIso?: unknown }).endIso === 'string'
    ) {
      out.range = {
        startIso: (p.range as { startIso: string }).startIso,
        endIso: (p.range as { endIso: string }).endIso,
      }
    }
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}

/**
 * Persist dashboard UI preferences (range as ISO strings).
 *
 * @param prefs - Selected date range for dashboard KPIs.
 * @returns {void} Nothing.
 */
export function saveDashboardPrefs(prefs: { range: DashboardRange }): void {
  if (!import.meta.client) {
    return
  }
  try {
    const payload: DashboardPrefsPersisted = {
      range: {
        startIso: prefs.range.start.toISOString(),
        endIso: prefs.range.end.toISOString(),
      },
    }
    localStorage.setItem(DASHBOARD_KEY, JSON.stringify(payload))
  } catch {
    /* */
  }
}

/**
 * Convert persisted ISO range strings back to `Date` bounds for the stats API.
 *
 * @param p - Stored `{ startIso, endIso }` payload.
 * @returns {DashboardRange | null} Valid inclusive range, or `null` if dates are invalid.
 */
export function dashboardPrefsToRange(p: DashboardPrefsPersisted['range']): DashboardRange | null {
  const start = new Date(p.startIso)
  const end = new Date(p.endIso)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) {
    return null
  }
  return { start, end }
}
