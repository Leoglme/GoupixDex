/** Valeur agrégée de la collection (cartes + produits scellés) : chiffres et courbes. */

export type PortfolioPeriod = '1j' | '7j' | '1m' | '3m' | '6m' | 'tout'

export interface PortfolioSplitSlice {
  label: string
  value: number
}

export interface PortfolioSummary {
  total_market_eur: number
  cards_market_eur: number
  sealed_market_eur: number
  purchase_value_eur: number
  sealed_gain_eur: number
  sealed_gain_percent: number | null
  split: PortfolioSplitSlice[]
  cards_count: number
  sealed_count: number
  sealed_total_quantity: number
  history_days: number
}

export interface PortfolioTimelinePoint {
  date: string
  market_eur: number
  purchase_eur: number
  cards_eur: number
  sealed_eur: number
}

export interface PortfolioTimelineResponse {
  period: PortfolioPeriod
  points: PortfolioTimelinePoint[]
}

/**
 * Composable « Valeur du portefeuille » (proxy GoupixDex authentifié).
 *
 * @returns Helpers async pour le résumé de valeur et les courbes d'évolution.
 */
export function usePortfolio() {
  const { $api } = useNuxtApp()

  /**
   * GET `/portfolio/summary` — chiffres vivants (valeur totale, répartition, plus-value scellés).
   *
   * @returns {Promise<PortfolioSummary>} Résumé de valeur.
   */
  async function getSummary() {
    const { data } = await $api.get<PortfolioSummary>('/portfolio/summary')
    return data
  }

  /**
   * GET `/portfolio/timeline` — historique de valeur pour les courbes, filtré par période.
   *
   * @param period - Fenêtre temporelle (`1j` | `7j` | `1m` | `3m` | `6m` | `tout`).
   * @returns {Promise<PortfolioTimelineResponse>} Points datés (marché, achat, cartes, scellés).
   */
  async function getTimeline(period: PortfolioPeriod = 'tout') {
    const { data } = await $api.get<PortfolioTimelineResponse>('/portfolio/timeline', {
      params: { period },
    })
    return data
  }

  return {
    getSummary,
    getTimeline,
  }
}
