import type { Ref } from 'vue'
import type { AxiosInstance } from 'axios'

export type EbaySoldTopCategory = 'cards' | 'graded' | 'sealed'

export interface EbaySoldTopRow {
  rank: number
  category: EbaySoldTopCategory
  fingerprint: string
  grade: string | null
  display_title: string
  image_url: string | null
  sample_listing_url: string | null
  count: number
  total_value_eur: number
  median_price_eur: number | null
  min_price_eur: number | null
  max_price_eur: number | null
  approx_hours_min: number | null
}

export interface EbaySoldTopResponse {
  query: string
  window_hours: number
  total_observed: number
  cards: EbaySoldTopRow[]
  graded: EbaySoldTopRow[]
  sealed: EbaySoldTopRow[]
  groups_count: { cards: number, graded: number, sealed: number }
  error: string | null
  ebay_sold_search_url: string
  source: string
}

export interface EbaySoldTopInput {
  q: string
  windowHours: number
  scrapeLimit?: number
  topLimit?: number
  minCount?: number
}

/**
 * Top des cartes / cartes gradées / items scellés vendus sur eBay.fr
 * (`GET /ebay/market/sold-top`), agrégés côté serveur depuis le scrape HTML public.
 *
 * @returns Reactive `loading` / `error` / `result`, plus `load` and `reset`.
 */
export function useEbaySoldTop() {
  const { $api } = useNuxtApp() as unknown as { $api: AxiosInstance }

  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const result: Ref<EbaySoldTopResponse | null> = ref(null)

  /**
   * Lance une requête top-sold ; remplit `result` ou positionne `error`.
   *
   * @param input - Paramètres de recherche.
   * @returns {Promise<EbaySoldTopResponse | null>} Payload API ou `null` en cas d'erreur.
   */
  async function load(input: EbaySoldTopInput): Promise<EbaySoldTopResponse | null> {
    loading.value = true
    error.value = null
    try {
      const { data } = await $api.get<EbaySoldTopResponse>('/ebay/market/sold-top', {
        params: {
          q: input.q.trim(),
          window_hours: input.windowHours,
          scrape_limit: input.scrapeLimit ?? 60,
          top_limit: input.topLimit ?? 20,
          min_count: input.minCount ?? 1
        },
        timeout: 120_000
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
   * Remet `result`, `error` et `loading` à zéro.
   *
   * @returns {void} Rien.
   */
  function reset(): void {
    result.value = null
    error.value = null
    loading.value = false
  }

  return { loading, error, result, load, reset }
}
