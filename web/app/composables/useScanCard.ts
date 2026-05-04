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

/**
 * OCR + pricing pipeline (`POST /scan-card`, multipart image upload).
 *
 * @returns `scan` helper posting `FormData` to the API.
 */
export function useScanCard() {
  const { $api } = useNuxtApp()

  /**
   * Upload a card photo for OCR, pricing, and listing preview fields.
   *
   * @param file - Image file from `<input type="file">` or drag-and-drop.
   * @param marginPercent - Margin percent forwarded as form field (default `20`).
   * @param ocrHint - Optional free-text hint for the OCR step.
   * @returns {Promise<ScanCardResponse>} Parsed OCR + pricing + listing preview payload.
   */
  async function scan(file: File, marginPercent = 20, ocrHint?: string) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('margin_percent', String(marginPercent))
    const hint = ocrHint?.trim()
    if (hint) {
      fd.append('ocr_hint', hint)
    }
    const { data } = await $api.post<ScanCardResponse>('/scan-card', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  }

  return { scan }
}
