/** Shipping label workflow: list eBay orders + render the A4 PDF preview/download. */

export interface EbayOrderAddress {
  full_name: string
  line1: string
  line2: string | null
  city: string
  state: string | null
  postal_code: string
  country_code: string
}

export interface EbayOrderItemSummary {
  title: string
  sku: string | null
  quantity: number
  line_item_id: string | null
}

export interface EbayUnshippedOrder {
  order_id: string
  creation_date: string | null
  order_fulfillment_status: string | null
  buyer_username: string | null
  address: EbayOrderAddress
  items: EbayOrderItemSummary[]
}

export interface ShippingLabelInput {
  full_name: string
  line1: string
  line2: string | null
  postal_code: string
  city: string
  state: string | null
  country_code: string | null
}

export function useShippingLabels() {
  const { $api } = useNuxtApp()

  async function fetchEbayOrders(): Promise<EbayUnshippedOrder[]> {
    const { data } = await $api.get<{ orders: EbayUnshippedOrder[], count: number }>(
      '/shipping/ebay-orders'
    )
    return data.orders ?? []
  }

  async function generateLabelsPdf(addresses: ShippingLabelInput[]): Promise<Blob> {
    const { data } = await $api.post<Blob>(
      '/shipping/labels.pdf',
      { addresses },
      { responseType: 'blob' }
    )
    return data
  }

  return {
    fetchEbayOrders,
    generateLabelsPdf
  }
}
