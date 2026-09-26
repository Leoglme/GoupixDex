import type { Ref } from 'vue'
import type {
  DesktopRelayClient,
  DesktopRelayClientMessage,
  DesktopRelayCommand,
  DesktopRelayResponse,
  DesktopRelayStreamEvent,
  DesktopRelayStreamHandlers,
  DesktopRelayStreamKind,
  DesktopWorkerName,
} from '~/types/DesktopRelay'

type PendingRelayRequest = {
  resolve: (response: DesktopRelayResponse) => void
  timer: ReturnType<typeof setTimeout>
}

type RelayStreamRegistration = {
  handlers: DesktopRelayStreamHandlers
  onOpened: () => void
}

type UnclaimedRelayMessages = {
  messages: DesktopRelayClientMessage[]
  receivedAt: number
}

const TOKEN_KEY: string = 'goupix_token'
const DEFAULT_REQUEST_TIMEOUT_MS: number = 35 * 60_000
const CONNECTION_TIMEOUT_MS: number = 6_000
const STREAM_OPEN_TIMEOUT_MS: number = 10_000
const RECONNECT_DELAY_MS: number = 15_000
const UNCLAIMED_MESSAGE_TTL_MS: number = 60_000

const isDesktopRelayOnline: Ref<boolean> = ref(false)
const hasDesktopRelayStatus: Ref<boolean> = ref(false)

let relayApiBase: string = ''
let relayClientId: string | null = null
let relayEventSource: EventSource | null = null
let firstRelayStatus: Promise<void> | null = null
let resolveFirstRelayStatus: (() => void) | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
const pendingRequests: Map<string, PendingRelayRequest> = new Map()
const streamRegistrations: Map<string, RelayStreamRegistration> = new Map()
const unclaimedMessages: Map<string, UnclaimedRelayMessages> = new Map()

/**
 * Lit le JWT de l'utilisateur connecté.
 * @returns {string | null} Le token, ou null hors navigateur ou déconnecté.
 */
function readToken(): string | null {
  return import.meta.client ? localStorage.getItem(TOKEN_KEY) : null
}

/**
 * Construit l'URL d'une route du relais sur l'API.
 * @param {string} path - Chemin sous `/desktop-relay` (avec sa query string).
 * @returns {string} URL absolue.
 */
function relayUrl(path: string): string {
  return `${relayApiBase}/desktop-relay${path}`
}

/**
 * POST JSON authentifié vers une route du relais.
 * @param {string} path - Chemin sous `/desktop-relay`.
 * @param {unknown} body - Corps JSON.
 * @returns {Promise<{ status: number; data: Record<string, unknown> }>} Statut HTTP et corps décodé.
 */
async function postToRelay(path: string, body: unknown): Promise<{ status: number; data: Record<string, unknown> }> {
  const token = readToken()
  try {
    const response = await fetch(relayUrl(path), {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    })
    const data = (await response.json().catch((): Record<string, unknown> => ({}))) as Record<string, unknown>
    return { status: response.status, data }
  } catch {
    return { status: 0, data: {} }
  }
}

/**
 * Garde un message arrivé avant que sa requête ou son flux soit enregistré (le PC a répondu très vite).
 * @param {string} id - Identifiant de requête ou de flux.
 * @param {DesktopRelayClientMessage} message - Message reçu.
 * @returns {void}
 */
function keepUnclaimedMessage(id: string, message: DesktopRelayClientMessage): void {
  const now = Date.now()
  for (const [unclaimedId, entry] of unclaimedMessages) {
    if (now - entry.receivedAt > UNCLAIMED_MESSAGE_TTL_MS) {
      unclaimedMessages.delete(unclaimedId)
    }
  }
  const entry = unclaimedMessages.get(id) ?? { messages: [], receivedAt: now }
  entry.messages.push(message)
  unclaimedMessages.set(id, entry)
}

/**
 * Récupère et oublie les messages arrivés en avance pour un identifiant.
 * @param {string} id - Identifiant de requête ou de flux.
 * @returns {DesktopRelayClientMessage[]} Messages dans leur ordre d'arrivée.
 */
function takeUnclaimedMessages(id: string): DesktopRelayClientMessage[] {
  const entry = unclaimedMessages.get(id)
  unclaimedMessages.delete(id)
  return entry?.messages ?? []
}

/**
 * Transmet un message du relais à la requête ou au flux qui l'attend.
 * @param {DesktopRelayClientMessage} message - Message reçu sur le flux SSE du client.
 * @returns {void}
 */
function dispatchRelayMessage(message: DesktopRelayClientMessage): void {
  if (message.type === 'agent-status') {
    isDesktopRelayOnline.value = message.online
    hasDesktopRelayStatus.value = true
    resolveFirstRelayStatus?.()
    return
  }
  if (message.type === 'connection-replaced') {
    return
  }

  if (message.type === 'response') {
    const pending = pendingRequests.get(message.id)
    if (!pending) {
      keepUnclaimedMessage(message.id, message)
      return
    }
    pendingRequests.delete(message.id)
    clearTimeout(pending.timer)
    pending.resolve(message)
    return
  }

  const registration = streamRegistrations.get(message.id)
  if (!registration) {
    keepUnclaimedMessage(message.id, message)
    return
  }
  if (message.type === 'stream-events') {
    registration.onOpened()
    const workerEvents = message.events.filter((event: DesktopRelayStreamEvent): boolean => event.event !== 'open')
    if (workerEvents.length) {
      registration.handlers.onEvents(workerEvents)
    }
    return
  }
  streamRegistrations.delete(message.id)
  registration.onOpened()
  registration.handlers.onEnd(message.error ?? null)
}

/**
 * Ouvre le flux SSE du relais pour cet onglet : réponses du PC, progression et présence du PC.
 * @returns {void}
 */
function connectDesktopRelay(): void {
  const token = readToken()
  if (!import.meta.client || relayEventSource || !token || !relayApiBase) {
    return
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  relayClientId = relayClientId ?? crypto.randomUUID()
  firstRelayStatus = new Promise((resolve: () => void): void => {
    resolveFirstRelayStatus = resolve
  })

  const query = new URLSearchParams({ token, client_id: relayClientId })
  const source = new EventSource(relayUrl(`/client/stream?${query.toString()}`))
  relayEventSource = source
  source.onmessage = (event: MessageEvent<string>): void => {
    try {
      dispatchRelayMessage(JSON.parse(event.data) as DesktopRelayClientMessage)
    } catch {
      // Trame illisible : ignorée.
    }
  }
  source.onerror = (): void => {
    if (source.readyState !== EventSource.CLOSED) {
      return
    }
    // Refusé (token expiré, accès retiré) : le navigateur ne réessaie plus de lui-même.
    relayEventSource = null
    isDesktopRelayOnline.value = false
    hasDesktopRelayStatus.value = true
    resolveFirstRelayStatus?.()
    reconnectTimer = setTimeout(connectDesktopRelay, RECONNECT_DELAY_MS)
  }
}

/**
 * Ferme le flux du relais et fait échouer ce qui attendait encore le PC.
 * @returns {void}
 */
function disconnectDesktopRelay(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  relayEventSource?.close()
  relayEventSource = null
  firstRelayStatus = null
  isDesktopRelayOnline.value = false
  hasDesktopRelayStatus.value = false
  for (const [requestId, pending] of pendingRequests) {
    clearTimeout(pending.timer)
    pending.resolve({ status: 503, error: 'desktop_offline' })
    pendingRequests.delete(requestId)
  }
  for (const [streamId, registration] of streamRegistrations) {
    streamRegistrations.delete(streamId)
    registration.onOpened()
    registration.handlers.onEnd('desktop_offline')
  }
}

/**
 * Ouvre le flux du relais si besoin et attend la première présence du PC.
 * @returns {Promise<boolean>} True quand le relais est connecté (le PC peut être hors ligne).
 */
async function ensureDesktopRelayConnected(): Promise<boolean> {
  connectDesktopRelay()
  if (!firstRelayStatus || !relayClientId) {
    return false
  }
  const timeout = new Promise<void>((resolve: () => void): void => {
    setTimeout(resolve, CONNECTION_TIMEOUT_MS)
  })
  await Promise.race([firstRelayStatus, timeout])
  return Boolean(relayEventSource)
}

/**
 * Fait exécuter un appel worker par le PC et attend sa réponse.
 * @param {DesktopRelayCommand} command - Worker, méthode, chemin et corps de l'appel.
 * @returns {Promise<DesktopRelayResponse>} Réponse du worker, ou statut 503/504 quand le PC ne répond pas.
 */
async function requestThroughDesktop(command: DesktopRelayCommand): Promise<DesktopRelayResponse> {
  const isConnected = await ensureDesktopRelayConnected()
  if (!isConnected || !isDesktopRelayOnline.value) {
    return { status: 503, error: 'desktop_offline' }
  }

  const submitted = await postToRelay('/requests', { client_id: relayClientId, ...command })
  if (submitted.status === 503) {
    isDesktopRelayOnline.value = false
    return { status: 503, error: 'desktop_offline' }
  }
  const requestId = submitted.data.request_id
  if (submitted.status !== 202 || typeof requestId !== 'string') {
    return { status: submitted.status || 503, error: 'relay_refused', data: submitted.data }
  }

  const earlyResponse = takeUnclaimedMessages(requestId).find(
    (message: DesktopRelayClientMessage): boolean => message.type === 'response',
  )
  if (earlyResponse && earlyResponse.type === 'response') {
    return earlyResponse
  }

  return new Promise((resolve: (response: DesktopRelayResponse) => void): void => {
    const timer = setTimeout((): void => {
      pendingRequests.delete(requestId)
      resolve({ status: 504, error: 'desktop_timeout' })
    }, command.timeout_ms ?? DEFAULT_REQUEST_TIMEOUT_MS)
    pendingRequests.set(requestId, { resolve, timer })
  })
}

/**
 * Demande au PC de suivre un flux de progression d'un worker et attend qu'il soit ouvert.
 * @param {DesktopWorkerName} worker - Worker concerné.
 * @param {DesktopRelayStreamKind} kind - `sse` ou `ws` selon le flux du worker.
 * @param {string} path - Chemin du flux sur le worker.
 * @param {DesktopRelayStreamHandlers} handlers - Réception des événements et de la fin du flux.
 * @returns {Promise<() => void>} Fonction qui arrête le flux.
 */
async function openDesktopStream(
  worker: DesktopWorkerName,
  kind: DesktopRelayStreamKind,
  path: string,
  handlers: DesktopRelayStreamHandlers,
): Promise<() => void> {
  const isConnected = await ensureDesktopRelayConnected()
  if (!isConnected || !isDesktopRelayOnline.value) {
    handlers.onEnd('desktop_offline')
    return (): void => {}
  }

  const opened = await postToRelay('/streams', { client_id: relayClientId, worker, kind, path })
  const streamId = opened.data.stream_id
  if (opened.status !== 202 || typeof streamId !== 'string') {
    handlers.onEnd(opened.status === 503 ? 'desktop_offline' : 'stream_refused')
    return (): void => {}
  }

  let resolveOpened: () => void = (): void => {}
  const openedOnDesktop = new Promise<void>((resolve: () => void): void => {
    resolveOpened = resolve
  })
  streamRegistrations.set(streamId, { handlers, onOpened: (): void => resolveOpened() })
  for (const message of takeUnclaimedMessages(streamId)) {
    dispatchRelayMessage(message)
  }

  const timeout = new Promise<void>((resolve: () => void): void => {
    setTimeout(resolve, STREAM_OPEN_TIMEOUT_MS)
  })
  await Promise.race([openedOnDesktop, timeout])

  return (): void => {
    if (!streamRegistrations.delete(streamId)) {
      return
    }
    const query = new URLSearchParams({ client_id: relayClientId ?? '' })
    const token = readToken()
    fetch(relayUrl(`/streams/${streamId}?${query.toString()}`), {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch((): void => {})
  }
}

/**
 * Relais vers l'app desktop du PC : présence du PC et exécution à distance des actions réservées au desktop.
 * @returns {DesktopRelayClient} État de présence, connexion, requêtes et flux relayés.
 */
export function useDesktopRelay(): DesktopRelayClient {
  if (!relayApiBase) {
    relayApiBase = String(useRuntimeConfig().public.apiBase || '').replace(/\/$/, '')
  }
  return {
    isDesktopRelayOnline,
    hasDesktopRelayStatus,
    connectDesktopRelay,
    disconnectDesktopRelay,
    waitForDesktopRelayStatus: ensureDesktopRelayConnected,
    requestThroughDesktop,
    openDesktopStream,
  }
}
