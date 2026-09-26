import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type {
  DesktopRelayHttpMethod,
  DesktopRelayRequest,
  DesktopRelayResponse,
  DesktopWorkerName,
} from '~/types/DesktopRelay'
import axios, { AxiosError, AxiosHeaders } from 'axios'
import { useDesktopRelay } from '~/composables/useDesktopRelay'
import { DESKTOP_RELAY_ERROR_CODE } from '~/composables/useApiError'

const TOKEN_KEY = 'goupix_token'
const MIN_RELAY_TIMEOUT_MS: number = 1_000
const MAX_RELAY_TIMEOUT_MS: number = 40 * 60_000
const PC_SESSION_EXPIRED_MESSAGE: string = "La session GoupixDex du PC a expiré : reconnectez-vous dans l'app du PC."
const RELAY_ERROR_MESSAGES: Record<string, string> = {
  desktop_offline: 'Ouvrez GoupixDex sur votre PC pour lancer cette action.',
  desktop_disconnected: "Le PC s'est déconnecté pendant l'action : vérifiez sur le PC qu'elle s'est terminée.",
  desktop_timeout: "Le PC n'a pas répondu à temps.",
  worker_unreachable: 'Le module local du PC ne répond pas : redémarrez GoupixDex sur le PC.',
  route_not_relayed: "Cette action n'est disponible que dans l'app desktop.",
}

/**
 * Reconvertit le corps sérialisé par axios pour l'envoyer au PC dans le JSON du relais.
 * @param {unknown} data - `config.data` après les transformations d'axios.
 * @returns {unknown} Corps JSON, ou undefined sans corps.
 * @throws {Error} Pour un envoi de fichiers, qui ne passe pas par le relais.
 */
function parseRelayedBody(data: unknown): unknown {
  if (data === undefined || data === null || data === '') {
    return undefined
  }
  if (typeof FormData !== 'undefined' && data instanceof FormData) {
    throw new Error("L'envoi de fichiers vers le PC n'est pas disponible depuis un autre appareil.")
  }
  if (typeof data !== 'string') {
    return data
  }
  try {
    return JSON.parse(data)
  } catch {
    return data
  }
}

/**
 * Transforme la réponse relayée par le PC en réponse axios.
 * @param {DesktopRelayResponse} relayed - Réponse du worker (ou erreur du relais).
 * @param {InternalAxiosRequestConfig} config - Configuration de la requête d'origine.
 * @returns {AxiosResponse} Réponse avec un `detail` lisible quand le PC n'a pas pu répondre.
 */
function toAxiosResponse(relayed: DesktopRelayResponse, config: InternalAxiosRequestConfig): AxiosResponse {
  const isPcSessionExpired = relayed.status === 401
  const relayErrorMessage = relayed.error ? RELAY_ERROR_MESSAGES[relayed.error] : undefined
  let data: unknown = relayed.data
  if (relayed.encoding === 'base64' && typeof relayed.data === 'string') {
    const bytes = Uint8Array.from(atob(relayed.data), (character: string): number => character.charCodeAt(0))
    data =
      config.responseType === 'arraybuffer' ? bytes.buffer : new Blob([bytes], { type: relayed.content_type ?? '' })
  }
  if (isPcSessionExpired || relayErrorMessage) {
    data = { detail: isPcSessionExpired ? PC_SESSION_EXPIRED_MESSAGE : relayErrorMessage }
  }
  return {
    data,
    // Un 401 du PC ne doit pas déconnecter l'appareil courant.
    status: isPcSessionExpired ? 502 : relayed.status,
    statusText: '',
    headers: new AxiosHeaders(relayed.content_type ? { 'content-type': relayed.content_type } : {}),
    config,
    request: null,
  }
}

/**
 * Code de l'erreur axios d'un appel relayé : un échec venu du PC porte un code à part, pour que les pages affichent son message.
 * @param {DesktopRelayResponse} relayed - Réponse du worker (ou erreur du relais).
 * @param {number} status - Statut de la réponse axios.
 * @returns {string} Code de l'erreur.
 */
function relayedErrorCode(relayed: DesktopRelayResponse, status: number): string {
  if (relayed.status === 401 || relayed.error) {
    return DESKTOP_RELAY_ERROR_CODE
  }
  return status >= 500 ? AxiosError.ERR_BAD_RESPONSE : AxiosError.ERR_BAD_REQUEST
}

/**
 * Adapter axios qui fait exécuter les appels d'un worker local par l'app desktop du PC, via le relais.
 * @param {DesktopWorkerName} worker - Worker ciblé par l'instance axios.
 * @param {DesktopRelayRequest} requestThroughDesktop - Envoi d'un appel au PC.
 * @returns {AxiosAdapter} Adapter à poser sur l'instance du worker.
 */
function createDesktopRelayAdapter(
  worker: DesktopWorkerName,
  requestThroughDesktop: DesktopRelayRequest,
): AxiosAdapter {
  return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    const target = new URL(axios.getUri(config))
    const isBinaryResponse = config.responseType === 'blob' || config.responseType === 'arraybuffer'
    const relayed = await requestThroughDesktop({
      worker,
      method: String(config.method ?? 'get').toUpperCase() as DesktopRelayHttpMethod,
      path: `${target.pathname}${target.search}`,
      body: parseRelayedBody(config.data),
      response_type: isBinaryResponse ? 'blob' : 'json',
      timeout_ms: config.timeout
        ? Math.min(Math.max(config.timeout, MIN_RELAY_TIMEOUT_MS), MAX_RELAY_TIMEOUT_MS)
        : undefined,
    })
    const response = toAxiosResponse(relayed, config)
    if (response.status >= 200 && response.status < 300) {
      return response
    }
    throw new AxiosError(
      `Request failed with status code ${response.status}`,
      relayedErrorCode(relayed, response.status),
      config,
      null,
      response,
    )
  }
}

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const token = useState<string | null>(TOKEN_KEY, () => null)

  if (import.meta.client) {
    token.value = localStorage.getItem(TOKEN_KEY)
  }

  const api = axios.create({
    baseURL: config.public.apiBase as string,
    headers: { Accept: 'application/json' },
  })

  const vintedLocal = axios.create({
    baseURL: (config.public.vintedLocalBase as string).replace(/\/$/, ''),
    headers: { Accept: 'application/json' },
  })

  const amazonLocal = axios.create({
    baseURL: (config.public.amazonLocalBase as string).replace(/\/$/, ''),
    headers: { Accept: 'application/json' },
  })

  const cardmarketLocal = axios.create({
    baseURL: (config.public.cardmarketLocalBase as string).replace(/\/$/, ''),
    headers: { Accept: 'application/json' },
  })

  const leboncoinLocal = axios.create({
    baseURL: (config.public.leboncoinLocalBase as string).replace(/\/$/, ''),
    headers: { Accept: 'application/json' },
    timeout: 30_000,
  })

  if (import.meta.client && !useDesktopRuntime().isDesktopApp.value) {
    const { requestThroughDesktop } = useDesktopRelay()
    vintedLocal.defaults.adapter = createDesktopRelayAdapter('vinted', requestThroughDesktop)
    amazonLocal.defaults.adapter = createDesktopRelayAdapter('amazon', requestThroughDesktop)
    cardmarketLocal.defaults.adapter = createDesktopRelayAdapter('cardmarket', requestThroughDesktop)
    leboncoinLocal.defaults.adapter = createDesktopRelayAdapter('leboncoin', requestThroughDesktop)
  }

  const attachAuth = (req: import('axios').InternalAxiosRequestConfig) => {
    const t = token.value ?? (import.meta.client ? localStorage.getItem(TOKEN_KEY) : null)
    if (t) {
      if (!req.headers) {
        req.headers = new axios.AxiosHeaders()
      }
      req.headers.Authorization = `Bearer ${t}`
    }
    return req
  }

  api.interceptors.request.use((req) => {
    attachAuth(req)
    return req
  })

  vintedLocal.interceptors.request.use((req) => {
    attachAuth(req)
    const apiBase = String(config.public.apiBase || '').replace(/\/$/, '')
    if (apiBase) {
      req.headers['X-Goupix-Remote-Api'] = apiBase
    }
    return req
  })

  amazonLocal.interceptors.request.use((req) => {
    attachAuth(req)
    const apiBase = String(config.public.apiBase || '').replace(/\/$/, '')
    if (apiBase) {
      req.headers['X-Goupix-Remote-Api'] = apiBase
    }
    return req
  })

  cardmarketLocal.interceptors.request.use((req) => {
    attachAuth(req)
    const apiBase = String(config.public.apiBase || '').replace(/\/$/, '')
    if (apiBase) {
      req.headers['X-Goupix-Remote-Api'] = apiBase
    }
    return req
  })

  leboncoinLocal.interceptors.request.use((req) => {
    attachAuth(req)
    const apiBase = String(config.public.apiBase || '').replace(/\/$/, '')
    if (apiBase) {
      req.headers['X-Goupix-Remote-Api'] = apiBase
    }
    return req
  })

  api.interceptors.response.use(
    (r) => r,
    (err) => {
      if (import.meta.client && err?.response?.status === 401) {
        localStorage.removeItem(TOKEN_KEY)
        token.value = null
        const path = window.location.pathname
        if (path !== '/login' && !path.startsWith('/login')) {
          navigateTo('/login')
        }
      }
      return Promise.reject(err)
    },
  )

  vintedLocal.interceptors.response.use(
    (r) => r,
    (err) => {
      if (import.meta.client && err?.response?.status === 401) {
        localStorage.removeItem(TOKEN_KEY)
        token.value = null
        const path = window.location.pathname
        if (path !== '/login' && !path.startsWith('/login')) {
          navigateTo('/login')
        }
      }
      return Promise.reject(err)
    },
  )

  amazonLocal.interceptors.response.use(
    (r) => r,
    (err) => {
      if (import.meta.client && err?.response?.status === 401) {
        localStorage.removeItem(TOKEN_KEY)
        token.value = null
        const path = window.location.pathname
        if (path !== '/login' && !path.startsWith('/login')) {
          navigateTo('/login')
        }
      }
      return Promise.reject(err)
    },
  )

  cardmarketLocal.interceptors.response.use(
    (r) => r,
    (err) => {
      if (import.meta.client && err?.response?.status === 401) {
        localStorage.removeItem(TOKEN_KEY)
        token.value = null
        const path = window.location.pathname
        if (path !== '/login' && !path.startsWith('/login')) {
          navigateTo('/login')
        }
      }
      return Promise.reject(err)
    },
  )

  leboncoinLocal.interceptors.response.use(
    (r) => r,
    (err) => {
      if (import.meta.client && err?.response?.status === 401) {
        localStorage.removeItem(TOKEN_KEY)
        token.value = null
        const path = window.location.pathname
        if (path !== '/login' && !path.startsWith('/login')) {
          navigateTo('/login')
        }
      }
      return Promise.reject(err)
    },
  )

  return {
    provide: {
      api,
      vintedLocal,
      amazonLocal,
      cardmarketLocal,
      leboncoinLocal,
    },
  }
})
