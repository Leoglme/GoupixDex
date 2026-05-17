export type DashboardPeriod = 'daily' | 'weekly' | 'monthly'

export interface DashboardRange {
  start: Date
  end: Date
}

export interface RevenueTimelinePoint {
  /** ISO datetime of the bucket start */
  date: string
  revenue_eur: number
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

export interface ChannelSplit {
  vinted_count: number
  ebay_count: number
  vinted_revenue_eur: number
  ebay_revenue_eur: number
}

export interface DashboardStats {
  range: {
    start: string
    end: string
    period: DashboardPeriod
  }
  /** Profit over the selected range. */
  profit_period_eur: number
  /** Sales revenue over the selected range. */
  revenue_period_eur: number
  /** Number of sales over the selected range. */
  period_sales_count: number
  profit_total_eur: number
  /** All-time sales revenue (kept for legacy callers). */
  vinted_revenue_eur: number
  /** Vinted vs eBay breakdown over the selected range. */
  channel_split_period: ChannelSplit
  /** Vinted vs eBay breakdown across all time. */
  channel_split_total: ChannelSplit
  inventory_count: number
  inventory_purchase_total_eur: number
  inventory_sell_total_eur: number
  /** Sum of (sell_price - purchase_price) for unsold articles with a price. */
  inventory_estimated_profit_eur: number
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

export interface FetchDashboardOptions {
  range?: DashboardRange
  period?: DashboardPeriod
}

export interface SoldSalesResponse {
  sales: RecentSaleRow[]
  count: number
  revenue_eur: number
  profit_eur: number
  vinted_count: number
  ebay_count: number
}

export type SoldSalesChannelFilter = 'vinted' | 'ebay' | null

/**
 * Serialize a `Date` as ISO string for dashboard query params.
 *
 * @param date - Range boundary from the date picker.
 * @returns {string} ISO timestamp string accepted by the API.
 */
function toIsoDate(date: Date): string {
  // Use a plain ISO datetime so the API can parse it back deterministically.
  return date.toISOString()
}

/**
 * Dashboard aggregates (`GET /stats/dashboard`).
 *
 * @returns `fetchDashboard` with optional range and timeline bucket size.
 */
export function useStats() {
  const { $api } = useNuxtApp()

  /**
   * Load dashboard KPIs for the selected window.
   *
   * @param options - Optional custom range and aggregation period for the revenue timeline.
   * @returns {Promise<DashboardStats>} Full dashboard payload from the API.
   */
  async function fetchDashboard(options: FetchDashboardOptions = {}) {
    const params: Record<string, string> = {}
    if (options.range) {
      params.start = toIsoDate(options.range.start)
      params.end = toIsoDate(options.range.end)
    }
    if (options.period) {
      params.period = options.period
    }
    const { data } = await $api.get<DashboardStats>('/stats/dashboard', { params })
    return data
  }

  /**
   * GET `/stats/sold-sales` — all sold articles (optional channel filter).
   *
   * @returns Sold sales list and aggregate totals for the selected channel.
   */
  async function fetchSoldSales(saleSource: SoldSalesChannelFilter = null) {
    const params: Record<string, string> = {}
    if (saleSource) {
      params.sale_source = saleSource
    }
    const { data } = await $api.get<SoldSalesResponse>('/stats/sold-sales', { params })
    return data
  }

  return { fetchDashboard, fetchSoldSales }
}
