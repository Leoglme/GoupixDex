/**
 * Saved Cardmarket panier searches (`/cardmarket-searches`).
 */
export interface CardmarketSearchListRow {
  id: number
  name: string | null
  created_at: string | null
  updated_at: string | null
  url_count: number
  last_ran_at: string | null
  max_seller_coverage: number | null
}

export interface CardmarketSearchUrlRow {
  id: number
  url: string
  sort_index: number
}

export interface CardmarketSearchDetail {
  id: number
  name: string | null
  created_at: string | null
  updated_at: string | null
  urls: CardmarketSearchUrlRow[]
  last_result: Record<string, unknown> | null
  last_ran_at: string | null
}

export type CardmarketSearchProgressPayload = {
  type?: string
  message?: string
  current?: number
  total?: number
  code?: string
  product_url?: string
  url?: string
  summary?: Record<string, unknown>
  payload?: Record<string, unknown>
}

/**
 * Single seller offer extracted from a Cardmarket product page.
 */
export interface CardmarketOfferRaw {
  seller_name: string
  price_eur: number
  quantity?: number | null
  seller_location?: string | null
  shipping_time_days?: number | null
  comments?: string | null
  article_id?: string | null
}

/**
 * One card in the panier with its scraped offers (`last_result.cards[]`).
 */
export interface CardmarketCardRaw {
  code: string
  product_name?: string | null
  product_url?: string | null
  warnings?: string[]
  offers: CardmarketOfferRaw[]
  cheapest_eur?: number | null
}

/**
 * One pick in the suggested basket (a single card bought from a chosen seller).
 */
export interface CardmarketBasketPick {
  code: string
  product_name: string | null
  product_url: string | null
  seller_name: string
  price_eur: number
  cheapest_eur: number | null
  delta_vs_min_eur: number | null
  delta_vs_min_percent: number | null
  is_best_price: boolean
}

/**
 * One seller block in the suggested basket (cards grouped under that seller).
 */
export interface CardmarketBasketSellerGroup {
  seller_name: string
  picks: CardmarketBasketPick[]
  subtotal_eur: number
}

/**
 * Card not covered by the suggested basket (no offer, no offer below overpay cap, or
 * over budget after greedy selection).
 */
export interface CardmarketBasketMissing {
  code: string
  product_name: string | null
  cheapest_eur: number | null
  reason: 'no_offer' | 'over_budget' | 'overpriced'
}

/**
 * Output of `suggestCardmarketBasket()` — full advisor result rendered in the UI.
 */
export interface CardmarketBasketSuggestion {
  budget_eur: number
  total_cards: number
  covered_cards: number
  total_price_eur: number
  remaining_budget_eur: number
  sellers: CardmarketBasketSellerGroup[]
  single_pick_seller_count: number
  missing: CardmarketBasketMissing[]
  warnings: string[]
}
