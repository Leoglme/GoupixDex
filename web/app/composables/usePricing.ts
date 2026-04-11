export interface PricingLookup {
  cardmarket_eur: number | null
  tcgplayer_usd: number | null
  average_price_eur: number | null
  suggested_price_eur: number | null
  margin_percent_used: number
  set_name: string | null
  error: string | null
}

export function usePricing() {
  const { $api } = useNuxtApp()

  async function lookup(
    setCode: string,
    cardNumber: string,
    pokemonName?: string | null
  ) {
    const { data } = await $api.get<PricingLookup>('/pricing/lookup', {
      params: {
        set_code: setCode,
        card_number: cardNumber,
        pokemon_name: pokemonName || undefined
      }
    })
    return data
  }

  /** Enrichit plusieurs articles avec la même clé (cache mémoire). */
  async function lookupMany(
    articles: Array<{
      id: number
      set_code: string | null
      card_number: string | null
      pokemon_name: string | null
    }>,
    concurrency = 4
  ): Promise<Map<number, PricingLookup>> {
    const out = new Map<number, PricingLookup>()
    const keyCache = new Map<string, PricingLookup>()

    const tasks = articles.filter(a => a.set_code && a.card_number)

    async function runOne(a: (typeof tasks)[0]) {
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
          error: 'Erreur réseau'
        })
      }
    }

    const queue = [...tasks]
    async function worker() {
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
