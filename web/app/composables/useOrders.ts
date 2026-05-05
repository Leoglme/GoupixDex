import type { OrderDetail, OrderListRow, OrderMatchResponse } from '~/types/Orders'

/**
 * Cardmarket orders API (import PDF, list, detail, match).
 *
 * @returns Typed REST helpers for `/orders`.
 */
export function useOrders() {
  const { $api } = useNuxtApp()

  /**
   * GET `/orders` — list orders for the current user.
   *
   * @param params.search - Optional filter (space-separated tokens: card, set, order id, seller…).
   * @returns Order rows for the dashboard table.
   */
  async function listOrders(params?: { search?: string }): Promise<OrderListRow[]> {
    const { data } = await $api.get<OrderListRow[]>('/orders', {
      params: params?.search !== undefined && params.search.trim() !== '' ? { search: params.search.trim() } : {},
    })
    return data
  }

  /**
   * GET `/orders/:id` — single order with lines.
   *
   * @param id - Internal order primary key.
   * @returns Full order payload.
   */
  async function getOrder(id: number): Promise<OrderDetail> {
    const { data } = await $api.get<OrderDetail>(`/orders/${id}`)
    return data
  }

  /**
   * POST `/orders/import` — upload Cardmarket PDF.
   *
   * @param file - PDF file from an `<input type="file">`.
   * @returns Imported order payload (same shape as GET detail).
   */
  async function importOrderPdf(file: File): Promise<OrderDetail> {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await $api.post<OrderDetail>('/orders/import', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  }

  /**
   * GET `/orders/match` — purchase lines matching article fields.
   *
   * @param params - Card identity fields (subset optional).
   * @returns FIFO suggestion + candidates for UI.
   */
  async function matchOrderLines(params: {
    pokemon_name?: string
    set_code?: string
    card_number?: string
    condition?: string
    language_code?: string
  }): Promise<OrderMatchResponse> {
    const { data } = await $api.get<OrderMatchResponse>('/orders/match', { params })
    return data
  }

  return { listOrders, getOrder, importOrderPdf, matchOrderLines }
}
