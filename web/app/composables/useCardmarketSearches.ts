import type { AxiosInstance } from 'axios'
import type {
  CardmarketSearchDetail,
  CardmarketSearchListRow,
  CardmarketSearchProgressPayload,
} from '~/types/CardmarketSearch'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'

/**
 * Remote API + local Cardmarket worker helpers.
 *
 * @returns CRUD helpers, progress WebSocket builder and run/cancel actions.
 */
export function useCardmarketSearches() {
  const nuxtApp = useNuxtApp() as {
    $api: AxiosInstance
    $cardmarketLocal: AxiosInstance
  }
  const { canUseDesktopWorkers, openWorkerSocketStream } = useDesktopWorkers()

  const api = computed(() => nuxtApp.$api)
  const local = computed(() => nuxtApp.$cardmarketLocal)

  /**
   * GET `/cardmarket-searches` — saved searches (with last-run summary).
   *
   * @returns Saved searches owned by the current user.
   */
  async function listSearches(): Promise<CardmarketSearchListRow[]> {
    const { data } = await api.value.get<CardmarketSearchListRow[]>('/cardmarket-searches')
    return data
  }

  /**
   * GET `/cardmarket-searches/:id` — full detail (URLs + last result payload).
   *
   * @param id Search id.
   * @returns Search detail including URLs and last scrape result.
   */
  async function getSearch(id: number): Promise<CardmarketSearchDetail> {
    const { data } = await api.value.get<CardmarketSearchDetail>(`/cardmarket-searches/${id}`)
    return data
  }

  /**
   * POST `/cardmarket-searches` — create a saved search from a list of URLs.
   *
   * @param body Optional name and Cardmarket product URLs.
   * @returns The newly created search detail.
   */
  async function createSearch(body: { name?: string | null; urls: string[] }): Promise<CardmarketSearchDetail> {
    const { data } = await api.value.post<CardmarketSearchDetail>('/cardmarket-searches', body)
    return data
  }

  /**
   * PUT `/cardmarket-searches/:id` — rename and/or replace the URL list.
   *
   * @param id   Search id.
   * @param body Fields to update (name and/or URLs).
   * @returns Updated search detail.
   */
  async function updateSearch(
    id: number,
    body: { name?: string | null; urls?: string[] },
  ): Promise<CardmarketSearchDetail> {
    const { data } = await api.value.put<CardmarketSearchDetail>(`/cardmarket-searches/${id}`, body)
    return data
  }

  /**
   *
   */
  async function deleteSearch(id: number): Promise<void> {
    await api.value.delete(`/cardmarket-searches/${id}`)
  }

  /**
   * Start a scrape run on the desktop worker (`POST …/run`).
   */
  async function startLocalRun(searchId: number): Promise<void> {
    if (!canUseDesktopWorkers.value) {
      throw new Error("L'analyse Cardmarket s'exécute sur votre PC : ouvrez GoupixDex sur votre ordinateur.")
    }
    await local.value.post(`/cardmarket-searches/${searchId}/run`)
  }

  /**
   * Cancel a running scrape on the desktop worker (`POST …/cancel`).
   */
  async function cancelLocalRun(searchId: number): Promise<void> {
    if (!canUseDesktopWorkers.value) {
      return
    }
    await local.value.post(`/cardmarket-searches/${searchId}/cancel`)
  }

  /**
   * Open progress WebSocket then start run; invoke `onPayload` until `done` / `error`.
   *
   * @returns Cleanup to close the socket.
   */
  async function runWithProgress(
    searchId: number,
    onPayload: (p: CardmarketSearchProgressPayload) => void,
  ): Promise<{ close: () => void }> {
    const progressChannel = await openWorkerSocketStream(
      'cardmarket',
      `/ws/cardmarket-searches/${encodeURIComponent(String(searchId))}/progress`,
      (data: string): void => {
        try {
          onPayload(JSON.parse(data) as CardmarketSearchProgressPayload)
        } catch {
          /* ignore malformed frames */
        }
      },
    )
    try {
      await startLocalRun(searchId)
    } catch (e) {
      progressChannel?.close()
      throw e
    }
    return {
      close: (): void => {
        progressChannel?.close()
      },
    }
  }

  return {
    listSearches,
    getSearch,
    createSearch,
    updateSearch,
    deleteSearch,
    startLocalRun,
    cancelLocalRun,
    runWithProgress,
    canUseDesktopWorkers,
  }
}
