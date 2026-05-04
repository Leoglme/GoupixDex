import type { Ref } from 'vue'
import type { AxiosInstance } from 'axios'

export type GradedFilter = 'raw' | 'psa' | 'cgc' | 'bgs' | 'all'
export type ConditionFilter = 'new' | 'used' | 'all'
export type SortOrder = 'price_asc' | 'price_desc' | 'relevance' | 'newly_listed'

export interface MarketGradedInfo {
  grader: string
  grade: string
}

export interface MarketStats {
  count: number
  min: number | null
  median: number | null
  max: number | null
  avg: number | null
}

export interface MarketListing {
  item_id: string
  title: string
  price_eur: number
  currency: string
  condition: string
  seller_username: string
  seller_country: string
  seller_feedback_score: number | null
  image_url: string | null
  listing_url: string
  buying_options: string[]
  graded: MarketGradedInfo | null
}

export interface MarketSearchResponse {
  query: string
  effective_query: string
  marketplace_id: string
  period_days: number
  filters_applied: {
    condition: ConditionFilter
    graded: GradedFilter
    sort: SortOrder
    fr_only: boolean
    min_price: number | null
    max_price: number | null
    limit: number
    exclude_keywords: string[]
    exclude_outliers: boolean
  }
  stats: MarketStats
  items: MarketListing[]
  outliers: MarketListing[]
  outliers_excluded: number
  total_matches: number
  warnings: string[]
}

export interface MarketSearchInput {
  q: string
  periodDays: number
  condition: ConditionFilter
  graded: GradedFilter
  sort: SortOrder
  frOnly: boolean
  minPrice: number | null
  maxPrice: number | null
  limit: number
}

/**
 * eBay France market price lookup (`GET /ebay/market/search`) via Browse API — OAuth is server-side.
 *
 * @returns Reactive `loading` / `error` / `result`, plus `search` and `reset`.
 */
export function useMarketSearch() {
  const { $api } = useNuxtApp() as unknown as { $api: AxiosInstance }

  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const result: Ref<MarketSearchResponse | null> = ref(null)

  /**
   * Run a market search with filters; stores `result` or sets `error` on failure.
   *
   * @param input - Query text, window, filters, and result limit.
   * @returns {Promise<MarketSearchResponse | null>} API payload on success, or `null` after error handling.
   */
  async function search(input: MarketSearchInput): Promise<MarketSearchResponse | null> {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string | number | boolean> = {
        q: input.q.trim(),
        period_days: input.periodDays,
        condition: input.condition,
        graded: input.graded,
        sort: input.sort,
        fr_only: input.frOnly,
        limit: input.limit,
      }
      if (input.minPrice != null) {
        params.min_price = input.minPrice
      }
      if (input.maxPrice != null) {
        params.max_price = input.maxPrice
      }
      const { data } = await $api.get<MarketSearchResponse>('/ebay/market/search', { params })
      result.value = data
      return data
    } catch (err: unknown) {
      const msg = apiErrorMessage(err)
      error.value = msg
      result.value = null
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Clear `result`, `error`, and `loading` — e.g. when leaving the page.
   *
   * @returns {void} Nothing.
   */
  function reset(): void {
    result.value = null
    error.value = null
    loading.value = false
  }

  return { loading, error, result, search, reset }
}
