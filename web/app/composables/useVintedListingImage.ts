import type { AxiosInstance } from 'axios'

/**
 * Télécharge une image listing via le worker local (contourne CORS CDN Vinted).
 */
export function useVintedListingImage() {
  const { $vintedLocal } = useNuxtApp()
  const client = computed(() => $vintedLocal as AxiosInstance)

  async function fetchBlob(url: string): Promise<Blob> {
    const { data } = await client.value.get<Blob>('/vinted/wardrobe-sync/listing-image', {
      params: { url },
      responseType: 'blob'
    })
    return data
  }

  return { fetchBlob }
}
