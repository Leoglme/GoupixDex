/**
 * Persistent UI preferences (localStorage), client-only.
 */

import type { DashboardPeriod, DashboardRange } from '~/composables/useStats'

const ARTICLES_LIST_KEY = 'goupix_articles_list_prefs'
const DASHBOARD_KEY = 'goupix_dashboard_prefs'

export type ArticleListFilterSold = 'all' | 'sold' | 'unsold'
export type ArticleListSortKey = 'created_desc' | 'sold_desc' | 'purchase_asc' | 'purchase_desc'

export interface ArticleListPrefs {
  filterSold: ArticleListFilterSold
  sortKey: ArticleListSortKey
  searchQuery: string
  /** My stock page: also show articles already for sale (default false if missing). */
  stockIncludeListed?: boolean
}

const SORT_KEYS: ArticleListSortKey[] = ['created_desc', 'sold_desc', 'purchase_asc', 'purchase_desc']

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
    if (p.filterSold === 'all' || p.filterSold === 'sold' || p.filterSold === 'unsold') {
      out.filterSold = p.filterSold
    }
    if (typeof p.sortKey === 'string' && SORT_KEYS.includes(p.sortKey as ArticleListSortKey)) {
      out.sortKey = p.sortKey as ArticleListSortKey
    }
    if (typeof p.searchQuery === 'string') {
      out.searchQuery = p.searchQuery
    }
    if (typeof p.stockIncludeListed === 'boolean') {
      out.stockIncludeListed = p.stockIncludeListed
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
  period: DashboardPeriod
  fetchMarketData: boolean
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
    if (p.period === 'daily' || p.period === 'weekly' || p.period === 'monthly') {
      out.period = p.period
    }
    if (typeof p.fetchMarketData === 'boolean') {
      out.fetchMarketData = p.fetchMarketData
    }
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}

/**
 * Persist dashboard UI preferences (range as ISO strings).
 *
 * @param prefs - Selected date range, stats period, and whether to include Cardmarket lookups.
 * @returns {void} Nothing.
 */
export function saveDashboardPrefs(prefs: {
  range: DashboardRange
  period: DashboardPeriod
  fetchMarketData: boolean
}): void {
  if (!import.meta.client) {
    return
  }
  try {
    const payload: DashboardPrefsPersisted = {
      range: {
        startIso: prefs.range.start.toISOString(),
        endIso: prefs.range.end.toISOString(),
      },
      period: prefs.period,
      fetchMarketData: prefs.fetchMarketData,
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
