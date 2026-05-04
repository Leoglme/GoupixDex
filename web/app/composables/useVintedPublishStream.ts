/**
 * Subscribes to the SSE stream ``GET /articles/:id/listing-progress`` after a listing
 * (Vinted and/or eBay). The event session lives on the remote API; the local worker
 * is only used for desktop Vinted publish (``sseBase: 'local'``).
 */
import type { Ref } from 'vue'

export type ListingStreamContext = 'create' | 'list' | 'logs'

export interface VintedLogEntry {
  text: string
  /** Data URL image/jpeg (browser capture). */
  screenshot?: string
}

export type ListingProgressSseBase = 'api' | 'local'

/**
 * Single-listing publish progress via SSE — logs, toasts, and optional local-worker hub.
 *
 * @returns `logEntries`, `logEl`, `followStream`, and `closeStream`.
 */
export function useVintedPublishStream() {
  const config = useRuntimeConfig()
  const { token } = useAuth()
  const toast = useToast()
  const { isDesktopApp } = useDesktopRuntime()

  const logEntries: Ref<VintedLogEntry[]> = ref([])
  const logEl: Ref<HTMLElement | null> = ref(null)

  let eventSource: EventSource | null = null

  watch(
    logEntries,
    async () => {
      await nextTick()
      const el = logEl.value
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    },
    { deep: true },
  )

  /**
   * Close the open SSE connection.
   *
   * @returns {void} Nothing.
   */
  function close(): void {
    eventSource?.close()
    eventSource = null
  }

  /**
   * Push one log row when `type === 'log'`.
   *
   * @param data - Parsed SSE fragment (`message`, optional `form_step`, `detail`, `screenshot`).
   * @returns {void} Nothing.
   */
  function pushLog(data: {
    type?: string
    message?: string
    step?: string
    form_step?: string
    detail?: string
    screenshot?: string
  }): void {
    if (data.type !== 'log' || typeof data.message !== 'string') {
      return
    }
    const tag = data.form_step ? `[${data.form_step}] ` : ''
    const extra = data.detail ? ` — ${data.detail}` : ''
    logEntries.value.push({
      text: `${tag}${data.message}${extra}`,
      screenshot: typeof data.screenshot === 'string' ? data.screenshot : undefined,
    })
  }

  /**
   * Open the listing-progress stream until `done` or `error`.
   *
   * @param streamPath - Absolute path under the hub (`/articles/.../listing-progress`).
   * @param context - Controls toast vs log-only UX (`logs` page stays silent on success toasts).
   * @param options - Optional `{ sseBase?: 'local' | 'api' }` to route via desktop worker.
   * @returns {Promise<void>} Resolves when the hub emits terminal events.
   */
  function followStream(
    streamPath: string,
    context: ListingStreamContext = 'list',
    options?: { sseBase?: ListingProgressSseBase },
  ): Promise<void> {
    close()
    logEntries.value = []
    const t = token.value ?? (import.meta.client ? localStorage.getItem('goupix_token') : null)
    if (!t) {
      return Promise.reject(new Error('Non authentifié'))
    }
    const remoteBase = (config.public.apiBase as string).replace(/\/$/, '')
    const localBase = String(config.public.vintedLocalBase || 'http://127.0.0.1:18766').replace(/\/$/, '')
    const useLocal = options?.sseBase === 'local' && isDesktopApp.value
    const base = useLocal ? localBase : remoteBase
    const remoteParam = isDesktopApp.value && useLocal ? `&remote_api=${encodeURIComponent(remoteBase)}` : ''
    const url = `${base}${streamPath}?token=${encodeURIComponent(t)}${remoteParam}`

    return new Promise((resolve, reject) => {
      let settled = false
      eventSource = new EventSource(url)

      eventSource.onmessage = (e: MessageEvent<string>) => {
        try {
          const data = JSON.parse(e.data) as {
            type?: string
            message?: string
            step?: string
            form_step?: string
            detail?: string
            screenshot?: string
            vinted?: { published?: boolean; detail?: string }
            ebay?: { published?: boolean; detail?: string; listing_id?: string }
          }
          if (data.type === 'log') {
            pushLog(data)
          } else if (data.type === 'done') {
            settled = true
            close()
            const v = data.vinted
            const eb = data.ebay
            if (context === 'logs') {
              // Publish journal: surface failures as log entries (otherwise
              // the user only sees a silent `done`).
              if (v && v.published === false) {
                const detail =
                  v.detail === 'missing_vinted_credentials'
                    ? "Identifiants Vinted manquants (profil ou variables d'environnement)."
                    : String(v.detail ?? 'Publication non confirmée.')
                logEntries.value.push({ text: `[Vinted · Erreur] ${detail}` })
              }
              if (eb && eb.published === false) {
                const detail = String(eb.detail ?? 'Échec ou annulation.')
                logEntries.value.push({ text: `[eBay · Erreur] ${detail}` })
              }
            }
            if (context !== 'logs') {
              if (v) {
                if (v.published) {
                  toast.add({
                    title: context === 'create' ? 'Article créé et publié sur Vinted' : 'Publié sur Vinted',
                    color: 'success',
                  })
                } else {
                  toast.add({
                    title: context === 'create' ? 'Article créé' : 'Publication Vinted',
                    description:
                      v?.detail === 'missing_vinted_credentials'
                        ? "Identifiants Vinted manquants (profil ou variables d'environnement)."
                        : String(v?.detail ?? 'Publication non confirmée.'),
                    color: 'warning',
                  })
                }
              }
              if (eb && typeof eb.published === 'boolean') {
                if (eb.published) {
                  toast.add({
                    title: context === 'create' ? 'Article créé et publié sur eBay' : 'Publié sur eBay',
                    color: 'success',
                  })
                } else {
                  toast.add({
                    title: 'Publication eBay',
                    description: String(eb.detail ?? 'Échec ou annulation.'),
                    color: 'warning',
                  })
                }
              }
            }
            resolve()
          } else if (data.type === 'error') {
            if (context === 'logs' && typeof data.message === 'string') {
              logEntries.value.push({ text: `[Erreur] ${data.message}` })
            }
            settled = true
            close()
            if (context !== 'logs') {
              toast.add({
                title: 'Flux publication',
                description: String(data.message ?? 'Erreur'),
                color: 'warning',
              })
            }
            resolve()
          }
        } catch {
          /* ignore parse errors */
        }
      }

      eventSource.onerror = () => {
        if (settled) {
          return
        }
        settled = true
        close()
        reject(new Error('Connexion au flux de publication interrompue'))
      }
    })
  }

  onBeforeUnmount(() => {
    close()
  })

  return { logEntries, logEl, followStream, closeStream: close }
}
