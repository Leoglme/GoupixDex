export interface ScanCardResponse {
  ocr: Record<string, unknown>
  pricing: {
    cardmarket_eur: number | null
    tcgplayer_usd: number | null
    average_price: number | null
    margin_percent_used: number
    suggested_price: number | null
    error: string | null
  }
  listing_preview: {
    title: string
    description: string
    suggested_price: number | null
  }
}

export function useScanCard() {
  const { $api } = useNuxtApp()

  async function scan(file: File, marginPercent = 20, ocrHint?: string) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('margin_percent', String(marginPercent))
    const hint = ocrHint?.trim()
    if (hint) {
      fd.append('ocr_hint', hint)
    }
    const { data } = await $api.post<ScanCardResponse>('/scan-card', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return data
  }

  return { scan }
}
