import type { AxiosInstance } from 'axios'
import type { OrdersSyncEvent } from '~/types/Orders'

const TOKEN_KEY = 'goupix_token'

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
  const config = useRuntimeConfig()
  const { isDesktopApp } = useDesktopRuntime()
  const local = computed(() => nuxtApp.$cardmarketLocal)

  /**
   * Build the WebSocket URL for `/ws/cardmarket/orders/sync/progress`.
   *
   * @returns Full URL with `token` and `remote_api`, or `null` on SSR or missing config.
   */
  function buildProgressWebSocketUrl(): string | null {
    if (!import.meta.client) {
      return null
    }
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token?.trim()) {
      return null
    }
    const base = String(config.public.cardmarketLocalBase || '').replace(/\/$/, '')
    const apiBase = String(config.public.apiBase || '').replace(/\/$/, '')
    if (!base || !apiBase) {
      return null
    }
    const wsBase = base.replace(/^http/i, (m) => (m.toLowerCase() === 'https' ? 'wss' : 'ws'))
    const q = new URLSearchParams({ token: token.trim(), remote_api: apiBase })
    return `${wsBase}/ws/cardmarket/orders/sync/progress?${q.toString()}`
  }

  /**
   * Open the WebSocket and resolve once it is open (or `null` on failure / timeout).
   *
   * @param onPayload - Called for every JSON event received.
   * @param openTimeoutMs - Maximum wait for `open`.
   * @returns Open socket, or `null` when URL/auth is missing or open times out.
   */
  async function openProgressSocket(
    onPayload: (ev: OrdersSyncEvent) => void,
    openTimeoutMs: number = 8000,
  ): Promise<WebSocket | null> {
    const url = buildProgressWebSocketUrl()
    if (!url) {
      return null
    }
    const ws = new WebSocket(url)

    ws.onmessage = (ev: MessageEvent): void => {
      try {
        const payload = JSON.parse(String(ev.data)) as OrdersSyncEvent
        onPayload(payload)
      } catch {
        /* ignore malformed frames */
      }
    }

    const opened = await new Promise<boolean>((resolve) => {
      const timer = window.setTimeout(() => resolve(false), openTimeoutMs)
      ws.onopen = (): void => {
        window.clearTimeout(timer)
        resolve(true)
      }
      ws.onerror = (): void => {
        window.clearTimeout(timer)
        resolve(false)
      }
    })

    if (!opened) {
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      return null
    }
    return ws
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
    if (!isDesktopApp.value) {
      throw new Error('La synchronisation Cardmarket nécessite l’application bureau GoupixDex.')
    }
    await local.value.post('/cardmarket/orders/sync')
  }

  /**
   * POST `/cardmarket/orders/sync/cancel` — cancel the running sync.
   */
  async function cancelSync(): Promise<void> {
    if (!isDesktopApp.value) {
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
    const ws = await openProgressSocket(onPayload)
    try {
      await startSync()
    } catch (e) {
      try {
        ws?.close()
      } catch {
        /* ignore */
      }
      throw e
    }
    return {
      close: (): void => {
        try {
          ws?.close()
        } catch {
          /* ignore */
        }
      },
    }
  }

  return {
    isDesktopApp,
    getActiveSync,
    startSync,
    cancelSync,
    openProgressSocket,
    runWithProgress,
  }
}
