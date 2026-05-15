import type { Ref } from 'vue'
import type { AxiosInstance } from 'axios'

export interface EbaySoldScrapeRow {
  title: string
  price_eur: number | null
  listing_url: string
  image_url: string | null
  item_id: string | null
  sold_caption: string | null
  approx_hours_ago: number | null
}

export interface EbaySoldScrapeResponse {
  query: string
  window_hours: number
  items: EbaySoldScrapeRow[]
  error: string | null
  ebay_sold_search_url: string
  source: string
}

export interface EbaySoldScrapeInput {
  q: string
  windowHours: number
  limit?: number
}

/**
 * eBay France sold-listings scrape (`GET /ebay/market/sold-scrape`) — public HTML
 * search, no Marketplace Insights OAuth.
 *
 * @returns Reactive `loading` / `error` / `result`, plus `load` and `reset`.
 */
export function useEbaySoldScrape() {
  const { $api } = useNuxtApp() as unknown as { $api: AxiosInstance }

  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const result: Ref<EbaySoldScrapeResponse | null> = ref(null)

  /**
   * Run a sold-listings scrape; stores `result` or sets `error` on failure.
   *
   * @param input - Query text, window in hours, and optional row limit.
   * @returns {Promise<EbaySoldScrapeResponse | null>} API payload on success, or `null` after error handling.
   */
  async function load(input: EbaySoldScrapeInput): Promise<EbaySoldScrapeResponse | null> {
    loading.value = true
    error.value = null
    try {
      const { data } = await $api.get<EbaySoldScrapeResponse>('/ebay/market/sold-scrape', {
        params: {
          q: input.q.trim(),
          window_hours: input.windowHours,
          limit: input.limit ?? 50,
        },
        timeout: 120_000,
      })
      result.value = data
      if (data.error) {
        error.value = data.error
      }
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

  return { loading, error, result, load, reset }
}
