import type { AxiosInstance } from 'axios'

/**
 * Proxy-download Vinted listing photos through the local worker (`GET .../listing-image`) to avoid CDN CORS.
 *
 * @returns `fetchBlob` bound to `$vintedLocal`.
 */
export function useVintedListingImage() {
  const { $vintedLocal } = useNuxtApp()
  const client = computed(() => $vintedLocal as AxiosInstance)

  /**
   * Fetch image bytes for a Vinted CDN URL.
   *
   * @param url - Absolute photo URL from wardrobe import payloads.
   * @returns {Promise<Blob>} Raw image body (`responseType: 'blob'`).
   */
  async function fetchBlob(url: string): Promise<Blob> {
    const { data } = await client.value.get<Blob>('/vinted/wardrobe-sync/listing-image', {
      params: { url },
      responseType: 'blob',
    })
    return data
  }

  return { fetchBlob }
}
