/**
 * Flux SSE local : ``GET /vinted/wardrobe-sync/jobs/:id/stream`` (worker desktop).
 */
export interface WardrobeSyncLogEntry {
  text: string
}

export function useWardrobeSyncStream() {
  const config = useRuntimeConfig()
  const { token } = useAuth()
  const { isDesktopApp } = useDesktopRuntime()

  const logEntries = ref<WardrobeSyncLogEntry[]>([])
  let eventSource: EventSource | null = null

  function close() {
    eventSource?.close()
    eventSource = null
  }

  /**
   * Suit le flux jusqu'à ``done`` (résultat sync) ou ``error``.
   */
  function followJobStream(jobId: string): Promise<Record<string, unknown>> {
    close()
    logEntries.value = []
    const t
      = token.value
        ?? (import.meta.client ? localStorage.getItem('goupix_token') : null)
    if (!t) {
      return Promise.reject(new Error('Non authentifié'))
    }
    const remoteBase = (config.public.apiBase as string).replace(/\/$/, '')
    const localBase = String(config.public.vintedLocalBase || 'http://127.0.0.1:18766').replace(
      /\/$/,
      ''
    )
    const base = isDesktopApp.value ? localBase : remoteBase
    const remoteParam = isDesktopApp.value
      ? `&remote_api=${encodeURIComponent(remoteBase)}`
      : ''
    const url = `${base}/vinted/wardrobe-sync/jobs/${encodeURIComponent(jobId)}/stream?token=${encodeURIComponent(t)}${remoteParam}`

    return new Promise((resolve, reject) => {
      let settled = false
      eventSource = new EventSource(url)

      eventSource.onmessage = (e: MessageEvent<string>) => {
        try {
          const data = JSON.parse(e.data) as {
            type?: string
            message?: string
            result?: Record<string, unknown>
          }
          if (data.type === 'log' && typeof data.message === 'string') {
            logEntries.value.push({ text: data.message })
          } else if (data.type === 'done') {
            settled = true
            close()
            resolve(data.result ?? {})
          } else if (data.type === 'error') {
            settled = true
            close()
            reject(new Error(String(data.message ?? 'Erreur synchronisation')))
          }
        } catch {
          /* ignore */
        }
      }

      eventSource.onerror = () => {
        if (settled) {
          return
        }
        settled = true
        close()
        reject(new Error('Connexion au flux garde-robe interrompue'))
      }
    })
  }

  onBeforeUnmount(() => {
    close()
  })

  return { logEntries, followJobStream, closeStream: close }
}
