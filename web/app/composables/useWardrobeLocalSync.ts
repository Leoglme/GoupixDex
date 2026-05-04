import type { AxiosInstance } from 'axios'

/**
 * Local worker (`$vintedLocal`): start wardrobe sync jobs and poll until completion.
 *
 * @returns `startJob` (POST job) and `pollUntilDone` (GET status loop).
 */
export function useWardrobeLocalSync() {
  const { $vintedLocal } = useNuxtApp()

  const client = computed(() => $vintedLocal as AxiosInstance)

  /**
   * POST `/vinted/wardrobe-sync/jobs` — enqueue a new scrape/import run.
   *
   * @returns {Promise<string>} New `job_id` string for SSE / polling.
   */
  async function startJob(): Promise<string> {
    const { data } = await client.value.post<{ job_id: string }>('/vinted/wardrobe-sync/jobs', {})
    return data.job_id
  }

  /**
   * Poll GET `/vinted/wardrobe-sync/jobs/:id` until `status === 'done'` or terminal error.
   *
   * @param jobId - Job returned by `startJob`.
   * @param pollOpts - Optional `{ intervalMs, maxAttempts }` loop tuning (defaults: 2s × 900).
   * @returns {Promise<Record<string, unknown>>} Worker `result` payload when done.
   */
  async function pollUntilDone(
    jobId: string,
    pollOpts?: { intervalMs?: number; maxAttempts?: number },
  ): Promise<Record<string, unknown>> {
    const intervalMs = pollOpts?.intervalMs ?? 2000
    const maxAttempts = pollOpts?.maxAttempts ?? 900
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
      await new Promise((r) => setTimeout(r, intervalMs))
    }
    throw new Error('Délai dépassé en attendant la synchronisation Vinted.')
  }

  return { startJob, pollUntilDone }
}
