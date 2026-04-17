import type { AxiosInstance } from 'axios'

/**
 * Worker local (port 18766) : démarrage + polling du job synchronisation garde-robe.
 */
export function useWardrobeLocalSync() {
  const { $vintedLocal } = useNuxtApp()

  const client = computed(() => $vintedLocal as AxiosInstance)

  async function startJob(): Promise<string> {
    const { data } = await client.value.post<{ job_id: string }>(
      '/vinted/wardrobe-sync/jobs',
      {}
    )
    return data.job_id
  }

  async function pollUntilDone(
    jobId: string,
    options?: { intervalMs?: number, maxAttempts?: number }
  ): Promise<Record<string, unknown>> {
    const intervalMs = options?.intervalMs ?? 2000
    const maxAttempts = options?.maxAttempts ?? 900
    for (let i = 0; i < maxAttempts; i++) {
      const { data } = await client.value.get<{
        status: string
        result?: Record<string, unknown>
        error?: string
      }>(`/vinted/wardrobe-sync/jobs/${jobId}`)
      if (data.status === 'done' && data.result) {
        return data.result
      }
      if (data.status === 'error') {
        throw new Error(data.error || 'Synchronisation Vinted interrompue.')
      }
      await new Promise(r => setTimeout(r, intervalMs))
    }
    throw new Error('Délai dépassé en attendant la synchronisation Vinted.')
  }

  return { startJob, pollUntilDone }
}
