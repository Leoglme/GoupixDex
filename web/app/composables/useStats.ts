export interface RevenueTimelinePoint {
  month: string
  revenue_month_eur: number
  revenue_cumulative_eur: number
}

export interface RecentSaleRow {
  article_id: number
  title: string
  pokemon_name: string | null
  sold_at: string | null
  /** Listed asking price on the listing. */
  listing_price_eur: number | null
  /** Actual proceeds when captured separately. */
  sold_price_eur: number | null
  /** Amount used for revenue / margin (sold_price or legacy sell_price). */
  realized_price_eur: number | null
  sale_source: 'vinted' | 'ebay' | null
  purchase_price_eur: number
  profit_eur: number
}

export interface DashboardStats {
  profit_week_eur: number
  profit_month_eur: number
  profit_total_eur: number
  vinted_revenue_eur: number
  inventory_count: number
  inventory_purchase_total_eur: number
  inventory_sell_total_eur: number
  estimated_cardmarket_inventory_eur: number | null
  estimated_cardmarket_unsold_eur: number | null
  market_lookup_errors: number
  revenue_timeline: RevenueTimelinePoint[]
  recent_sales: RecentSaleRow[]
  top_profitable: Array<{
    article_id: number
    title: string
    pokemon_name: string | null
    profit_eur: number
  }>
  fastest_sold: Array<{
    article_id: number
    title: string
    pokemon_name: string | null
    hours_to_sell: number
  }>
}

export function useStats() {
  const { $api } = useNuxtApp()

  async function fetchDashboard(includeMarket = false) {
    const { data } = await $api.get<DashboardStats>('/stats/dashboard', {
      params: { include_market: includeMarket }
    })
    return data
  }

  return { fetchDashboard }
}
