export interface DashboardStats {
  profit_week_eur: number
  profit_month_eur: number
  profit_total_eur: number
  vinted_revenue_eur: number
  estimated_cardmarket_inventory_eur: number | null
  market_lookup_errors: number
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
  weekly_sold_profit: Array<{ week: string, profit_eur: number }>
}

export function useStats() {
  const { $api } = useNuxtApp()

  async function fetchDashboard(includeMarket = true) {
    const { data } = await $api.get<DashboardStats>('/stats/dashboard', {
      params: { include_market: includeMarket }
    })
    return data
  }

  return { fetchDashboard }
}
