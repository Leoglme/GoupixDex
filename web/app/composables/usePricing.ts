export interface PricingLookup {
  cardmarket_eur: number | null
  tcgplayer_usd: number | null
  average_price_eur: number | null
  suggested_price_eur: number | null
  margin_percent_used: number
  set_name: string | null
  error: string | null
}

/**
 * Card pricing lookups (`GET /pricing/lookup`) with optional batched enrichment.
 *
 * @returns `lookup` for one article key and `lookupMany` with concurrency + in-memory cache.
 */
export function usePricing() {
  const { $api } = useNuxtApp()

  /**
   * Fetch pricing stats for a single card identity.
   *
   * @param setCode - Pokémon TCG set code.
   * @param cardNumber - Collector number within the set.
   * @param pokemonName - Optional name hint for disambiguation.
   * @returns {Promise<PricingLookup>} Normalized pricing payload from the API.
   */
  async function lookup(setCode: string, cardNumber: string, pokemonName?: string | null) {
    const { data } = await $api.get<PricingLookup>('/pricing/lookup', {
      params: {
        set_code: setCode,
        card_number: cardNumber,
        pokemon_name: pokemonName || undefined,
      },
    })
    return data
  }

  /**
   * Enrich many articles in parallel (bounded concurrency), caching by `(set|card|name)` key.
   *
   * @param articles - Rows with `id`, `set_code`, `card_number`, `pokemon_name`.
   * @param concurrency - Max parallel `lookup` calls (default `4`).
   * @returns {Promise<Map<number, PricingLookup>>} Article id → pricing row (errors filled with a stub row).
   */
  async function lookupMany(
    articles: Array<{
      id: number
      set_code: string | null
      card_number: string | null
      pokemon_name: string | null
    }>,
    concurrency = 4,
  ): Promise<Map<number, PricingLookup>> {
    const out = new Map<number, PricingLookup>()
    const keyCache = new Map<string, PricingLookup>()

    const tasks = articles.filter((a) => a.set_code && a.card_number)

    /**
     * Resolve pricing for one article and populate `out` / `keyCache`.
     *
     * @param a - Article row with non-null set + card number.
     * @returns {Promise<void>} Nothing.
     */
    async function runOne(a: (typeof tasks)[0]): Promise<void> {
      const k = `${a.set_code}|${a.card_number}|${a.pokemon_name || ''}`
      if (keyCache.has(k)) {
        out.set(a.id, keyCache.get(k)!)
        return
      }
      try {
        const p = await lookup(a.set_code!, a.card_number!, a.pokemon_name)
        keyCache.set(k, p)
        out.set(a.id, p)
      } catch {
        out.set(a.id, {
          cardmarket_eur: null,
          tcgplayer_usd: null,
          average_price_eur: null,
          suggested_price_eur: null,
          margin_percent_used: 0,
          set_name: null,
          error: 'Erreur réseau',
        })
      }
    }

    const queue = [...tasks]
    /**
     * Worker draining the shared queue until empty.
     *
     * @returns {Promise<void>} Nothing.
     */
    async function worker(): Promise<void> {
      while (queue.length) {
        const a = queue.shift()
        if (a) {
          await runOne(a)
        }
      }
    }
    const n = Math.max(1, Math.min(concurrency, tasks.length))
    await Promise.all(Array.from({ length: n }, () => worker()))
    return out
  }

  return { lookup, lookupMany }
}
