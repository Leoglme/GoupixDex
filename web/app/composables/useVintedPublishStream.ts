/**
 * Connexion au flux SSE `/articles/:id/vinted-progress` après lancement d'une publication.
 */
export type VintedStreamContext = 'create' | 'list' | 'logs'

export interface VintedLogEntry {
  text: string
  /** Data URL image/jpeg (capture navigateur). */
  screenshot?: string
}

export function useVintedPublishStream() {
  const config = useRuntimeConfig()
  const { token } = useAuth()
  const toast = useToast()
  const { isDesktopApp } = useDesktopRuntime()

  const logEntries = ref<VintedLogEntry[]>([])
  const logEl = ref<HTMLElement | null>(null)

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
    { deep: true }
  )

  function close() {
    eventSource?.close()
    eventSource = null
  }

  function pushLog(data: {
    type?: string
    message?: string
    step?: string
    form_step?: string
    detail?: string
    screenshot?: string
  }) {
    if (data.type !== 'log' || typeof data.message !== 'string') {
      return
    }
    const tag = data.form_step ? `[${data.form_step}] ` : ''
    const extra = data.detail ? ` — ${data.detail}` : ''
    logEntries.value.push({
      text: `${tag}${data.message}${extra}`,
      screenshot: typeof data.screenshot === 'string' ? data.screenshot : undefined
    })
  }

  /**
   * Ouvre le flux jusqu'à l'événement ``done`` ou ``error``.
   */
  function followStream(
    streamPath: string,
    context: VintedStreamContext = 'list'
  ): Promise<void> {
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
            vinted?: { published?: boolean, detail?: string }
          }
          if (data.type === 'log') {
            pushLog(data)
          } else if (data.type === 'done') {
            settled = true
            close()
            const v = data.vinted
            if (context !== 'logs') {
              if (v?.published) {
                toast.add({
                  title:
                    context === 'create'
                      ? 'Article créé et publié sur Vinted'
                      : 'Publié sur Vinted',
                  color: 'success'
                })
              } else {
                toast.add({
                  title: context === 'create' ? 'Article créé' : 'Publication Vinted',
                  description:
                    v?.detail === 'missing_vinted_credentials'
                      ? "Identifiants Vinted manquants (profil ou variables d'environnement)."
                      : String(v?.detail ?? 'Publication non confirmée.'),
                  color: 'warning'
                })
              }
            }
            resolve()
          } else if (data.type === 'error') {
            settled = true
            close()
            if (context !== 'logs') {
              toast.add({
                title: 'Flux publication',
                description: String(data.message ?? 'Erreur'),
                color: 'warning'
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

  return { logEntries, logEl, followStream, closeStream: close }
}
