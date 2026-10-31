import type { Marketplace } from '~/types/Marketplace'

export type DashboardPeriod = 'daily' | 'weekly' | 'monthly'

export type DashboardRange = {
  start: Date
  end: Date
}

export type SalesTimelinePoint = {
  /** ISO datetime of the bucket start */
  date: string
  revenue_eur: number
  profit_eur: number
  sales_count: number
}

export type SaleRow = {
  article_id: number
  title: string
  pokemon_name: string | null
  image_url: string | null
  sold_at: string | null
  /** Listed asking price on the listing. */
  listing_price_eur: number | null
  /** Actual proceeds when captured separately. */
  sold_price_eur: number | null
  /** Amount used for revenue / margin (sold_price or legacy sell_price). */
  realized_price_eur: number | null
  sale_source: Marketplace | null
  purchase_price_eur: number
  profit_eur: number
  hours_to_sell: number | null
}

export type InventoryArticleRow = {
  article_id: number
  title: string
  pokemon_name: string | null
  image_url: string | null
  created_at: string | null
  sell_price_eur: number | null
}

export type ChannelSales = {
  sale_source: Marketplace
  revenue_eur: number
  profit_eur: number
  sales_count: number
}

export type DashboardPreviousPeriod = {
  start: string
  end: string
  revenue_eur: number
  profit_eur: number
  sales_count: number
}

export type DashboardStats = {
  range: {
    start: string
    end: string
    period: DashboardPeriod
  }
  /** Sales revenue over the selected range. */
  revenue_period_eur: number
  /** Profit over the selected range. */
  profit_period_eur: number
  /** Number of sales over the selected range. */
  period_sales_count: number
  median_hours_to_sell: number | null
  previous_period: DashboardPreviousPeriod | null
  sales_by_channel: ChannelSales[]
  sales_timeline: SalesTimelinePoint[]
  recent_sales: SaleRow[]
  top_profitable: SaleRow[]
  fastest_sold: SaleRow[]
  inventory_count: number
  inventory_purchase_total_eur: number
  inventory_sell_total_eur: number
  /** Sum of (sell_price - purchase_price) for unsold articles with a price. */
  inventory_estimated_profit_eur: number
  inventory_longest_listed: InventoryArticleRow[]
}

export interface SoldSalesResponse {
  sales: SaleRow[]
  count: number
  revenue_eur: number
  profit_eur: number
  vinted_count: number
  ebay_count: number
  leboncoin_count: number
}

export type SoldSalesChannelFilter = Marketplace | null

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
 * @returns `fetchDashboard` for the selected range and `fetchSoldSales`.
 */
export function useStats() {
  const { $api } = useNuxtApp()

  /**
   * Charge les ventes de la période et le stock en vente, découpés selon le fuseau horaire du navigateur.
   *
   * @param range - Période choisie dans le tableau de bord.
   * @returns {Promise<DashboardStats>} Full dashboard payload from the API.
   */
  async function fetchDashboard(range: DashboardRange): Promise<DashboardStats> {
    const params: Record<string, string> = {
      start: toIsoDate(range.start),
      end: toIsoDate(range.end),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
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
