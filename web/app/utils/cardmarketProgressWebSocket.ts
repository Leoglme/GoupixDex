import type { CardmarketSearchProgressPayload } from '~/types/CardmarketSearch'

/**
 * WebSocket `/ws/cardmarket-searches/:id/progress` on the local Cardmarket worker.
 * @param wsUrl - Full URL with `token` and `remote_api` query params.
 * @param onPayload - Handler for each JSON frame.
 * @param openTimeoutMs - Max wait for socket open.
 * @returns Connected socket or `null`.
 */
export async function openCardmarketProgressWebSocket(
  wsUrl: string,
  onPayload: (payload: CardmarketSearchProgressPayload) => void,
  openTimeoutMs: number = 8000,
): Promise<WebSocket | null> {
  if (!import.meta.client || !/^wss?:\/\//i.test(wsUrl)) {
    return null
  }

  const ws = new WebSocket(wsUrl)

  ws.onmessage = (ev: MessageEvent): void => {
    try {
      const payload = JSON.parse(String(ev.data)) as CardmarketSearchProgressPayload
      onPayload(payload)
    } catch {
      /* ignore */
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
