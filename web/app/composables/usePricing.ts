export interface PricingLookup {
  cardmarket_eur: number | null
  tcgplayer_usd: number | null
  /** TCGPlayer converted with server ``USD_TO_EUR`` (same basis as moyenne). */
  tcgplayer_eur: number | null
  average_price_eur: number | null
  suggested_price_eur: number | null
  margin_percent_used: number
  set_name: string | null
  error: string | null
}

/**
 * Card pricing lookup (`GET /pricing/lookup`) — PokéWallet (Cardmarket / TCGPlayer) + marge pour prix suggéré.
 *
 * @returns {object} Objet contenant la fonction `lookup` pour charger les prix catalogue.
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

  return { lookup }
}
