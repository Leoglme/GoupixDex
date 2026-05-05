/**
 * Row returned by GET /orders (list view).
 */
export interface OrderListRow {
  id: number
  external_order_id: string
  seller_username: string | null
  seller_display_name: string | null
  seller_country_code: string | null
  paid_at: string | null
  shipped_at: string | null
  delivered_at: string | null
  items_subtotal: number
  shipping_fee: number
  order_total: number
  line_count: number
  item_units: number
  sold_articles_count: number
  created_at: string
}

/**
 * Linked article summary on an order line (detail page).
 */
export interface OrderDetailArticleRef {
  id: number
  title: string
  is_sold: boolean
  sold_at: string | null
}

/**
 * Line item on GET /orders/:id.
 */
export interface OrderDetailLine {
  id: number
  line_index: number
  quantity: number
  raw_label: string
  pokemon_key: string | null
  card_number: string | null
  language_code: string | null
  condition_label: string | null
  set_code: string | null
  variant_token: string | null
  unit_price_eur: number
  remaining_units: number
  articles: OrderDetailArticleRef[]
}

/**
 * Full order payload from GET /orders/:id or POST /orders/import.
 */
export interface OrderDetail {
  id: number
  external_order_id: string
  seller_username: string | null
  seller_display_name: string | null
  seller_country_code: string | null
  paid_at: string | null
  shipped_at: string | null
  delivered_at: string | null
  items_subtotal: number
  shipping_fee: number
  order_total: number
  /** Sum of sold prices (sold articles linked to this order). */
  sales_revenue_eur: number
  source_filename: string | null
  created_at: string
  sold_articles_count: number
  lines: OrderDetailLine[]
}

/**
 * GET /orders/match response for article create prefill.
 */
export interface OrderMatchResponse {
  candidates: Array<{
    order_line_id: number
    order_id: number
    external_order_id: string
    paid_at: string | null
    unit_price_eur: number
    remaining_units: number
  }>
  fifo_order_line_id: number | null
  latest_purchase_order_line_id: number | null
  suggested_purchase_price: number | null
}
