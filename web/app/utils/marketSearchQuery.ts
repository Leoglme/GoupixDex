import type { LocationQuery } from 'vue-router'
import type { ConditionFilter, GradedFilter, MarketSearchInput, SortOrder } from '~/composables/useMarketSearch'

/** Defaults aligned with fiche article + lien « Prix du marché » (neuf + occasion). */
export const DEFAULT_ARTICLE_MARKET_SEARCH_BASE: Omit<MarketSearchInput, 'q'> = {
  periodDays: 30,
  condition: 'all',
  graded: 'all',
  sort: 'relevance',
  frOnly: false,
  minPrice: null,
  maxPrice: null,
  limit: 50,
}

/**
 * Parse `MarketSearchInput` from `/market` query string (prefill + auto-search).
 * @param query - `route.query`
 * @returns Payload when `q` is valid, otherwise `null`.
 */
export function parseMarketSearchFromQuery(query: LocationQuery): MarketSearchInput | null {
  const q = String(query.q ?? '').trim()
  if (q.length < 2) {
    return null
  }

  const pd = Number(query.period_days)
  const periodDays = Number.isFinite(pd) ? Math.min(365, Math.max(0, Math.trunc(pd))) : 30

  const lim = Number(query.limit)
  const limit = Number.isFinite(lim) ? Math.min(200, Math.max(1, Math.trunc(lim))) : 50

  const c = String(query.condition ?? '')
  const condition: ConditionFilter = c === 'new' || c === 'used' || c === 'all' ? c : 'all'

  const g = String(query.graded ?? '')
  const graded: GradedFilter = g === 'raw' || g === 'psa' || g === 'cgc' || g === 'bgs' || g === 'all' ? g : 'all'

  const s = String(query.sort ?? '')
  const sort: SortOrder =
    s === 'price_asc' || s === 'price_desc' || s === 'relevance' || s === 'newly_listed' ? s : 'relevance'

  const frOnly = query.fr_only === '1' || query.fr_only === 'true' || query.fr_only === true

  const minRaw = query.min_price
  const maxRaw = query.max_price
  const minPrice = minRaw != null && minRaw !== '' ? parseFloat(String(minRaw).replace(',', '.')) : null
  const maxPrice = maxRaw != null && maxRaw !== '' ? parseFloat(String(maxRaw).replace(',', '.')) : null

  return {
    q,
    periodDays,
    condition,
    graded,
    sort,
    frOnly,
    minPrice: minPrice != null && Number.isFinite(minPrice) && minPrice >= 0 ? minPrice : null,
    maxPrice: maxPrice != null && Number.isFinite(maxPrice) && maxPrice >= 0 ? maxPrice : null,
    limit,
  }
}

/**
 * Build `/market` query object for `navigateTo` / `<NuxtLink :to>` from a search payload.
 * @param input - Same shape as `MarketSearchInput`
 * @param autoSearch - When true, page runs search on load (`auto=1`).
 * @returns Vue Router query record (string values).
 */
export function marketSearchToRouteQuery(input: MarketSearchInput, autoSearch: boolean): Record<string, string> {
  const q: Record<string, string> = {
    q: input.q,
    period_days: String(input.periodDays),
    condition: input.condition,
    graded: input.graded,
    sort: input.sort,
    fr_only: input.frOnly ? '1' : '0',
    limit: String(input.limit),
  }
  if (autoSearch) {
    q.auto = '1'
  }
  if (input.minPrice != null) {
    q.min_price = String(input.minPrice)
  }
  if (input.maxPrice != null) {
    q.max_price = String(input.maxPrice)
  }
  return q
}
