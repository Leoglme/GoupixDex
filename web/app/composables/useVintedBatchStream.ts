/**
 * SSE consumer for ``GET /articles/vinted-batch/{job_id}/stream``: logs + ``progress`` events.
 */
import type { Ref } from 'vue'
import type { VintedLogEntry } from '~/composables/useVintedPublishStream'

export interface VintedBatchProgress {
  current: number
  total: number
  articleId?: number
  title?: string
}

/**
 * Multi-article Vinted publish job stream (desktop worker or API relay) with scroll-sticky logs.
 *
 * @returns Log refs, progress, `followBatchStream`, and explicit close helpers.
 */
export function useVintedBatchStream() {
  const config = useRuntimeConfig()
  const { token } = useAuth()
  const toast = useToast()
  const { isDesktopApp } = useDesktopRuntime()

  const logEntries: Ref<VintedLogEntry[]> = ref([])
  const logEl: Ref<HTMLElement | null> = ref(null)
  const progress: Ref<VintedBatchProgress | null> = ref(null)
  const finished: Ref<boolean> = ref(false)
  const lastSummary: Ref<unknown> = ref(null)

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
   * Tear down the active `EventSource`, if any.
   *
   * @returns {void} Nothing.
   */
  function close(): void {
    eventSource?.close()
    eventSource = null
  }

  /**
   * Append one structured log line coming from SSE JSON payloads.
   *
   * @param data - Parsed message body (`type`, `message`, optional `form_step`, `detail`, `screenshot`).
   * @returns {void} Nothing.
   */
  function pushLog(data: {
    type?: string
    message?: string
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
   * Subscribe to the batch SSE URL until `done` / `error` / transport failure.
   *
   * @param streamPath - Path suffix including job id (from `startVintedBatch`).
   * @param opts - Optional `{ quiet?: boolean }` to suppress completion toasts.
   * @returns {Promise<void>} Resolves when the server closes the stream normally.
   */
  function followBatchStream(streamPath: string, opts?: { quiet?: boolean }): Promise<void> {
    close()
    logEntries.value = []
    progress.value = null
    finished.value = false
    lastSummary.value = null

    const t = token.value ?? (import.meta.client ? localStorage.getItem('goupix_token') : null)
    if (!t) {
      return Promise.reject(new Error('Non authentifié'))
    }
    const remoteBase = (config.public.apiBase as string).replace(/\/$/, '')
    const localBase = String(config.public.vintedLocalBase || 'http://127.0.0.1:18766').replace(/\/$/, '')
    const base = isDesktopApp.value ? localBase : remoteBase
    const remoteParam = isDesktopApp.value ? `&remote_api=${encodeURIComponent(remoteBase)}` : ''
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
            current?: number
            total?: number
            article_id?: number
            title?: string
            summary?: unknown
            vinted?: { published?: boolean; detail?: string }
          }
          if (data.type === 'progress') {
            const cur = data.current ?? 0
            const tot = data.total ?? 0
            progress.value = {
              current: cur,
              total: tot,
              articleId: data.article_id,
              title: data.title,
            }
            return
          }
          if (data.type === 'log') {
            pushLog(data)
            return
          }
          if (data.type === 'done') {
            settled = true
            finished.value = true
            lastSummary.value = data.summary ?? data
            close()
            const v = data.vinted
            if (!opts?.quiet) {
              if (v?.published) {
                toast.add({
                  title: 'Lot Vinted terminé',
                  description: 'Toutes les annonces prévues ont été publiées.',
                  color: 'success',
                })
              } else {
                toast.add({
                  title: 'Lot Vinted terminé',
                  description:
                    v?.detail === 'missing_vinted_credentials'
                      ? "Identifiants Vinted manquants (profil ou variables d'environnement)."
                      : String(v?.detail ?? 'Publication partielle ou non confirmée.'),
                  color: 'warning',
                })
              }
            }
            resolve()
            return
          }
          if (data.type === 'error') {
            settled = true
            finished.value = true
            close()
            if (!opts?.quiet) {
              toast.add({
                title: 'Flux publication groupée',
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
        reject(new Error('Connexion au flux Vinted interrompue'))
      }
    })
  }

  onBeforeUnmount(() => {
    close()
  })

  return {
    logEntries,
    logEl,
    progress,
    finished,
    lastSummary,
    followBatchStream,
    closeBatchStream: close,
  }
}
