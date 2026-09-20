import axios from 'axios'
import { resolveProvisionInboundApiBase } from '~/utils/provisionInboundApiBase'

const TOKEN_KEY = 'goupix_token'

/**
 *
 */
export function useAmazonProvisionInbound() {
  const config = useRuntimeConfig()
  const token = useState<string | null>(TOKEN_KEY, () => null)

  /**
   *
   */
  function inboundClient() {
    const baseURL = resolveProvisionInboundApiBase(
      String(config.public.apiBase || ''),
      config.public.provisionInboundApiBase as string | undefined,
    )
    const client = axios.create({
      baseURL,
      headers: { Accept: 'application/json' },
    })
    client.interceptors.request.use((req) => {
      const t = token.value ?? (import.meta.client ? localStorage.getItem(TOKEN_KEY) : null)
      if (t) {
        req.headers.Authorization = `Bearer ${t}`
      }
      return req
    })
    return client
  }

  /**
   *
   */
  async function registerInboundWatch(email: string): Promise<void> {
    await inboundClient().post('/amazon-accounts/provision/inbound-watch', { email })
  }

  /**
   *
   */
  async function fetchInboundCode(email: string): Promise<string | null> {
    const { data } = await inboundClient().get<{ email: string; code: string | null }>(
      '/amazon-accounts/provision/inbound-code',
      { params: { email } },
    )
    return data.code?.trim() || null
  }

  /**
   *
   */
  function pollInboundCode(
    email: string,
    onCode: (code: string) => void,
    intervalMs = 2500,
    maxMs = 20 * 60_000,
  ): () => void {
    const started = Date.now()
    let stopped = false
    const tick = async () => {
      if (stopped || Date.now() - started > maxMs) {
        return
      }
      try {
        const code = await fetchInboundCode(email)
        if (code) {
          onCode(code)
          return
        }
      } catch {
        /* watch pas encore actif ou API indisponible */
      }
      if (!stopped) {
        window.setTimeout(tick, intervalMs)
      }
    }
    void tick()
    return () => {
      stopped = true
    }
  }

  return {
    registerInboundWatch,
    fetchInboundCode,
    pollInboundCode,
    provisionInboundApiBase: computed(() =>
      resolveProvisionInboundApiBase(
        String(config.public.apiBase || ''),
        config.public.provisionInboundApiBase as string | undefined,
      ),
    ),
  }
}
