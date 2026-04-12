/**
 * Connexion au flux SSE `/articles/:id/vinted-progress` après lancement d'une publication.
 */
export type VintedStreamContext = 'create' | 'list'

export function useVintedPublishStream() {
  const config = useRuntimeConfig()
  const { token } = useAuth()
  const toast = useToast()

  const logs = ref<string[]>([])
  const logEl = ref<HTMLElement | null>(null)

  let eventSource: EventSource | null = null

  watch(
    logs,
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

  /**
   * Ouvre le flux jusqu'à l'événement ``done`` ou ``error``.
   * @param context - ``create`` : toasts combinés création + Vinted ; ``list`` : publication depuis la liste.
   */
  function followStream(
    streamPath: string,
    context: VintedStreamContext = 'list'
  ): Promise<void> {
    close()
    logs.value = []
    const t
      = token.value
        ?? (import.meta.client ? localStorage.getItem('goupix_token') : null)
    if (!t) {
      return Promise.reject(new Error('Non authentifié'))
    }
    const base = (config.public.apiBase as string).replace(/\/$/, '')
    const url = `${base}${streamPath}?token=${encodeURIComponent(t)}`

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
            vinted?: { published?: boolean, detail?: string }
          }
          if (data.type === 'log' && typeof data.message === 'string') {
            const tag = data.form_step ? `[${data.form_step}] ` : ''
            const extra = data.detail ? ` — ${data.detail}` : ''
            logs.value.push(`${tag}${data.message}${extra}`)
          } else if (data.type === 'done') {
            settled = true
            close()
            const v = data.vinted
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
            resolve()
          } else if (data.type === 'error') {
            settled = true
            close()
            toast.add({
              title: 'Flux publication',
              description: String(data.message ?? 'Erreur'),
              color: 'warning'
            })
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

  return { logs, logEl, followStream, closeStream: close }
}
