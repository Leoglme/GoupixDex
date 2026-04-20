/**
 * Préférences UI persistantes (localStorage), usage client uniquement.
 */

import type { DashboardPeriod, DashboardRange } from '~/composables/useStats'

const ARTICLES_LIST_KEY = 'goupix_articles_list_prefs'
const DASHBOARD_KEY = 'goupix_dashboard_prefs'

export type ArticleListFilterSold = 'all' | 'sold' | 'unsold'
export type ArticleListSortKey =
  | 'created_desc'
  | 'sold_desc'
  | 'purchase_asc'
  | 'purchase_desc'
  | 'cm_asc'
  | 'cm_desc'

export interface ArticleListPrefs {
  filterSold: ArticleListFilterSold
  sortKey: ArticleListSortKey
  searchQuery: string
}

const SORT_KEYS: ArticleListSortKey[] = [
  'created_desc',
  'sold_desc',
  'purchase_asc',
  'purchase_desc',
  'cm_asc',
  'cm_desc'
]

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
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}

export function saveArticleListPrefs(prefs: ArticleListPrefs) {
  if (!import.meta.client) {
    return
  }
  try {
    localStorage.setItem(ARTICLES_LIST_KEY, JSON.stringify(prefs))
  } catch {
    /* quota / private mode */
  }
}

export interface DashboardPrefsPersisted {
  range: { startIso: string, endIso: string }
  period: DashboardPeriod
  fetchMarketData: boolean
}

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
      p.range
      && typeof p.range === 'object'
      && p.range !== null
      && typeof (p.range as { startIso?: unknown }).startIso === 'string'
      && typeof (p.range as { endIso?: unknown }).endIso === 'string'
    ) {
      out.range = {
        startIso: (p.range as { startIso: string }).startIso,
        endIso: (p.range as { endIso: string }).endIso
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

export function saveDashboardPrefs(data: {
  range: DashboardRange
  period: DashboardPeriod
  fetchMarketData: boolean
}) {
  if (!import.meta.client) {
    return
  }
  try {
    const payload: DashboardPrefsPersisted = {
      range: {
        startIso: data.range.start.toISOString(),
        endIso: data.range.end.toISOString()
      },
      period: data.period,
      fetchMarketData: data.fetchMarketData
    }
    localStorage.setItem(DASHBOARD_KEY, JSON.stringify(payload))
  } catch {
    /* */
  }
}

export function dashboardPrefsToRange(p: DashboardPrefsPersisted['range']): DashboardRange | null {
  const start = new Date(p.startIso)
  const end = new Date(p.endIso)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) {
    return null
  }
  return { start, end }
}
