import type { AmazonWorkerProgressPayload } from '~/types/amazonWorkerProgress'

/**
 * Open `/ws/progress` on the Amazon local worker and forward JSON payloads.
 * @param wsUrl - Full WebSocket URL including `token` and `remote_api` query params.
 * @param onPayload - Called for each JSON message from the worker.
 * @param openTimeoutMs - Max wait for the socket to open (refresh still runs if this fails).
 * @returns Connected socket, or `null` if URL was invalid or open failed.
 */
export async function openAmazonProgressWebSocket(
  wsUrl: string,
  onPayload: (payload: AmazonWorkerProgressPayload) => void,
  openTimeoutMs: number = 5000,
): Promise<WebSocket | null> {
  if (!import.meta.client || !/^wss?:\/\//i.test(wsUrl)) {
    return null
  }

  const ws = new WebSocket(wsUrl)

  ws.onmessage = (ev: MessageEvent): void => {
    try {
      const payload = JSON.parse(String(ev.data)) as AmazonWorkerProgressPayload
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
