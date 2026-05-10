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
