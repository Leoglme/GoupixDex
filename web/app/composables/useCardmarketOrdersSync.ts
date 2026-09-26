import type { AxiosInstance } from 'axios'
import type { WorkerProgressChannel } from '~/types/DesktopRelay'
import type { OrdersSyncEvent } from '~/types/Orders'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'

/**
 * Drive the local Cardmarket worker's "sync purchases" job.
 *
 * Mirrors `useCardmarketSearches`: a `POST` triggers the worker, a WebSocket
 * streams progress, and a `cancel` POST stops the run.
 *
 * @returns Helpers to start, observe and cancel a sync run.
 */
export function useCardmarketOrdersSync() {
  const nuxtApp = useNuxtApp() as { $cardmarketLocal: AxiosInstance }
  const { canUseDesktopWorkers, openWorkerSocketStream } = useDesktopWorkers()
  const local = computed(() => nuxtApp.$cardmarketLocal)

  /**
   * Open the sync progress stream (on the PC, or relayed) and resolve once it is open.
   *
   * @param onPayload - Called for every JSON event received.
   * @param openTimeoutMs - Maximum wait for `open`.
   * @returns Open channel, or `null` when the worker does not answer.
   */
  async function openProgressSocket(
    onPayload: (ev: OrdersSyncEvent) => void,
    openTimeoutMs: number = 8000,
  ): Promise<WorkerProgressChannel | null> {
    return openWorkerSocketStream(
      'cardmarket',
      '/ws/cardmarket/orders/sync/progress',
      (data: string): void => {
        try {
          onPayload(JSON.parse(data) as OrdersSyncEvent)
        } catch {
          /* ignore malformed frames */
        }
      },
      { openTimeoutMs },
    )
  }

  /**
   * GET `/cardmarket/orders/sync/active` — whether a sync is already running for the user.
   *
   * @returns `{ active, last_event }` for resuming the UI on page reload.
   */
  async function getActiveSync(): Promise<{ active: boolean; last_event: OrdersSyncEvent | null }> {
    const { data } = await local.value.get<{ active: boolean; last_event: OrdersSyncEvent | null }>(
      '/cardmarket/orders/sync/active',
    )
    return data
  }

  /**
   * POST `/cardmarket/orders/sync` — start the sync job on the local worker.
   * Throws if not on desktop or if a sync is already running (409).
   */
  async function startSync(): Promise<void> {
    if (!canUseDesktopWorkers.value) {
      throw new Error('La synchronisation Cardmarket s’exécute sur votre PC : ouvrez GoupixDex sur votre ordinateur.')
    }
    await local.value.post('/cardmarket/orders/sync')
  }

  /**
   * POST `/cardmarket/orders/sync/cancel` — cancel the running sync.
   */
  async function cancelSync(): Promise<void> {
    if (!canUseDesktopWorkers.value) {
      return
    }
    try {
      await local.value.post('/cardmarket/orders/sync/cancel')
    } catch {
      /* swallow 404 if no run is active */
    }
  }

  /**
   * Open a progress socket then start the sync (`runWithProgress` pattern).
   *
   * @param onPayload - Handler for streamed events.
   * @returns Cleanup `close()` to drop the WebSocket from the caller side.
   */
  async function runWithProgress(onPayload: (ev: OrdersSyncEvent) => void): Promise<{ close: () => void }> {
    const progressChannel = await openProgressSocket(onPayload)
    try {
      await startSync()
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
    canUseDesktopWorkers,
    getActiveSync,
    startSync,
    cancelSync,
    openProgressSocket,
    runWithProgress,
  }
}
