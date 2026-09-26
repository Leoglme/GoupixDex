import type { AxiosInstance, AxiosResponse } from 'axios'
import type {
  DesktopRelayAgent,
  DesktopRelayAgentMessage,
  DesktopRelayHttpMethod,
  DesktopRelayStreamEvent,
  DesktopWorkerName,
  RelayedRequestMessage,
  RelayedStreamOpenMessage,
  RelayedWorkerRoute,
  WorkerProgressChannel,
} from '~/types/DesktopRelay'

const TOKEN_KEY: string = 'goupix_token'
const RECONNECT_DELAY_MS: number = 15_000
const STREAM_FLUSH_DELAY_MS: number = 150

// Seules ces routes des workers sont exécutables depuis un autre appareil.
const RELAYED_WORKER_ROUTES: Record<DesktopWorkerName, RelayedWorkerRoute[]> = {
  vinted: [
    { method: 'GET', path: /^\/health$/ },
    { method: 'POST', path: /^\/articles\/\d+\/(publish-vinted|remove-vinted-listing|vinted-unlist-after-ebay-sale)$/ },
    { method: 'GET', path: /^\/articles\/vinted-batch\/active$/ },
    { method: 'POST', path: /^\/articles\/vinted-batch(-delist|-refresh)?$/ },
    { method: 'POST', path: /^\/vinted\/wardrobe-sync\/jobs$/ },
    { method: 'GET', path: /^\/vinted\/wardrobe-sync\/jobs\/[\w-]+$/ },
    { method: 'GET', path: /^\/vinted\/wardrobe-sync\/listing-image$/ },
  ],
  leboncoin: [
    { method: 'POST', path: /^\/articles\/\d+\/publish-leboncoin$/ },
    { method: 'GET', path: /^\/leboncoin\/(meta|session)$/ },
  ],
  cardmarket: [
    { method: 'GET', path: /^\/health$/ },
    { method: 'GET', path: /^\/cardmarket-searches\/\d+\/run\/active$/ },
    { method: 'POST', path: /^\/cardmarket-searches\/\d+\/(run|cancel)$/ },
    { method: 'GET', path: /^\/cardmarket\/orders\/sync\/active$/ },
    { method: 'POST', path: /^\/cardmarket\/orders\/sync(\/cancel)?$/ },
    { method: 'GET', path: /^\/cardmarket\/session$/ },
  ],
  amazon: [
    { method: 'GET', path: /^\/health$/ },
    { method: 'GET', path: /^\/amazon\/(meta|session|invites)$/ },
    { method: 'POST', path: /^\/amazon\/invites\/(refresh|reverify|verify-all|request)$/ },
  ],
}

const RELAYED_WORKER_STREAMS: Record<DesktopWorkerName, RegExp[]> = {
  vinted: [
    /^\/articles\/\d+\/listing-progress$/,
    /^\/articles\/vinted-batch\/[\w-]+\/stream$/,
    /^\/vinted\/wardrobe-sync\/jobs\/[\w-]+\/stream$/,
  ],
  leboncoin: [/^\/articles\/\d+\/listing-progress$/],
  cardmarket: [/^\/ws\/cardmarket\/orders\/sync\/progress$/, /^\/ws\/cardmarket-searches\/\d+\/progress$/],
  amazon: [/^\/ws\/progress$/],
}

let agentEventSource: EventSource | null = null
let agentReconnectTimer: ReturnType<typeof setTimeout> | null = null
const relayedStreamStoppers: Map<string, () => void> = new Map()

/**
 * Encode un corps binaire (photo proxifiée) pour le transporter en JSON.
 * @param {ArrayBuffer} buffer - Octets reçus du worker.
 * @returns {string} Contenu en base64.
 */
function encodeBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000))
  }
  return btoa(binary)
}

/**
 * Dit si une trame SSE de worker termine son flux (`done` ou `error`).
 * @param {string} data - Trame brute du worker.
 * @returns {boolean} True pour la dernière trame d'une publication, d'un lot ou d'un import.
 */
function isFinalWorkerEvent(data: string): boolean {
  try {
    const parsed = JSON.parse(data) as { type?: string }
    return parsed.type === 'done' || parsed.type === 'error'
  } catch {
    return false
  }
}

/**
 * Agent de l'app desktop : exécute sur les workers du PC les actions lancées depuis un autre appareil du même compte.
 * @returns {DesktopRelayAgent} Démarrage et arrêt de l'agent.
 */
export function useDesktopRelayAgent(): DesktopRelayAgent {
  const config = useRuntimeConfig()
  const { isDesktopApp } = useDesktopRuntime()
  const { $api, $vintedLocal, $amazonLocal, $cardmarketLocal, $leboncoinLocal } = useNuxtApp()
  const { openWorkerEventStream, openWorkerSocketStream } = useDesktopWorkers()

  const workerClients: Record<DesktopWorkerName, AxiosInstance> = {
    vinted: $vintedLocal as AxiosInstance,
    amazon: $amazonLocal as AxiosInstance,
    cardmarket: $cardmarketLocal as AxiosInstance,
    leboncoin: $leboncoinLocal as AxiosInstance,
  }

  /**
   * Vérifie qu'une route de worker fait partie de celles relayées.
   * @param {DesktopWorkerName} worker - Worker visé.
   * @param {DesktopRelayHttpMethod} method - Méthode HTTP.
   * @param {string} path - Chemin demandé (query string comprise).
   * @returns {boolean} True si l'appel peut être exécuté.
   */
  function isRelayedRoute(worker: DesktopWorkerName, method: DesktopRelayHttpMethod, path: string): boolean {
    const pathname = path.split('?')[0] ?? ''
    return RELAYED_WORKER_ROUTES[worker].some(
      (route: RelayedWorkerRoute): boolean => route.method === method && route.path.test(pathname),
    )
  }

  /**
   * Vérifie qu'un flux de progression de worker fait partie de ceux relayés.
   * @param {DesktopWorkerName} worker - Worker visé.
   * @param {string} path - Chemin du flux.
   * @returns {boolean} True si le flux peut être suivi.
   */
  function isRelayedStream(worker: DesktopWorkerName, path: string): boolean {
    const pathname = path.split('?')[0] ?? ''
    return RELAYED_WORKER_STREAMS[worker].some((pattern: RegExp): boolean => pattern.test(pathname))
  }

  /**
   * Exécute un appel worker relayé et renvoie sa réponse à l'appareil qui l'a demandé.
   * @param {RelayedRequestMessage} message - Appel reçu du relais.
   * @returns {Promise<void>}
   */
  async function answerRelayedRequest(message: RelayedRequestMessage): Promise<void> {
    if (!isRelayedRoute(message.worker, message.method, message.path)) {
      await $api.post('/desktop-relay/agent/responses', {
        request_id: message.id,
        status: 403,
        error: 'route_not_relayed',
      })
      return
    }

    const isBinaryResponse = message.response_type === 'blob'
    let response: AxiosResponse
    try {
      response = await workerClients[message.worker].request({
        method: message.method,
        url: message.path,
        data: message.body ?? undefined,
        responseType: isBinaryResponse ? 'arraybuffer' : 'json',
        timeout: message.timeout_ms ?? 0,
        validateStatus: (): boolean => true,
      })
    } catch {
      await $api.post('/desktop-relay/agent/responses', {
        request_id: message.id,
        status: 502,
        error: 'worker_unreachable',
      })
      return
    }

    await $api.post('/desktop-relay/agent/responses', {
      request_id: message.id,
      status: response.status,
      data: isBinaryResponse ? encodeBase64(response.data as ArrayBuffer) : response.data,
      content_type: String(response.headers['content-type'] ?? '') || null,
      encoding: isBinaryResponse ? 'base64' : 'json',
    })
  }

  /**
   * Suit un flux de progression local et en transmet les trames (regroupées) à l'appareil distant.
   * @param {RelayedStreamOpenMessage} message - Ouverture de flux reçue du relais.
   * @returns {void}
   */
  function relayWorkerStream(message: RelayedStreamOpenMessage): void {
    const pendingEvents: DesktopRelayStreamEvent[] = []
    let sendingChain: Promise<void> = Promise.resolve()
    let flushTimer: ReturnType<typeof setTimeout> | null = null
    let isFinished = false
    let stopLocalStream: () => void = (): void => {}

    const flushPendingEvents = (): void => {
      flushTimer = null
      if (!pendingEvents.length) {
        return
      }
      const events = pendingEvents.splice(0, pendingEvents.length)
      sendingChain = sendingChain.then(async (): Promise<void> => {
        try {
          const { data } = await $api.post<{ delivered: boolean }>('/desktop-relay/agent/stream-events', {
            stream_id: message.id,
            events,
          })
          if (!data.delivered) {
            stopRelayedStream()
          }
        } catch {
          // Coupure réseau : ces trames sont perdues, le flux continue.
        }
      })
    }

    const pushEvent = (event: DesktopRelayStreamEvent): void => {
      if (isFinished) {
        return
      }
      pendingEvents.push(event)
      flushTimer = flushTimer ?? setTimeout(flushPendingEvents, STREAM_FLUSH_DELAY_MS)
    }

    const stopRelayedStream = (): void => {
      isFinished = true
      relayedStreamStoppers.delete(message.id)
      stopLocalStream()
      if (flushTimer) {
        clearTimeout(flushTimer)
        flushTimer = null
      }
    }

    const finishRelayedStream = (error: string | null): void => {
      if (isFinished) {
        return
      }
      if (flushTimer) {
        clearTimeout(flushTimer)
      }
      flushPendingEvents()
      stopRelayedStream()
      sendingChain = sendingChain.then(async (): Promise<void> => {
        await $api.post('/desktop-relay/agent/stream-end', { stream_id: message.id, error }).catch((): void => {})
      })
    }

    if (!isRelayedStream(message.worker, message.path)) {
      finishRelayedStream('stream_not_relayed')
      return
    }
    relayedStreamStoppers.set(message.id, stopRelayedStream)

    if (message.kind === 'sse') {
      const source = openWorkerEventStream(message.worker, message.path)
      stopLocalStream = (): void => source.close()
      source.onopen = (): void => pushEvent({ event: 'open', data: '' })
      source.onmessage = (event: MessageEvent<string>): void => {
        pushEvent({ data: event.data })
        if (isFinalWorkerEvent(event.data)) {
          finishRelayedStream(null)
        }
      }
      source.onerror = (): void => finishRelayedStream('worker_stream_closed')
      return
    }

    openWorkerSocketStream(message.worker, message.path, (data: string): void => pushEvent({ data }), {
      authSubprotocol: message.worker === 'amazon',
    }).then((channel: WorkerProgressChannel | null): void => {
      if (!channel) {
        finishRelayedStream('worker_unreachable')
        return
      }
      if (isFinished) {
        channel.close()
        return
      }
      stopLocalStream = (): void => channel.close()
      pushEvent({ event: 'open', data: '' })
    })
  }

  /**
   * Traite une commande reçue du relais.
   * @param {DesktopRelayAgentMessage} message - Commande décodée.
   * @returns {void}
   */
  function handleAgentMessage(message: DesktopRelayAgentMessage): void {
    if (message.type === 'request') {
      answerRelayedRequest(message).catch((): void => {})
    } else if (message.type === 'stream-open') {
      relayWorkerStream(message)
    } else if (message.type === 'stream-close') {
      relayedStreamStoppers.get(message.id)?.()
    } else if (message.type === 'connection-replaced') {
      // Une autre app desktop du même compte a pris le relais : pas de reconnexion.
      stopDesktopRelayAgent()
    }
  }

  /**
   * Connecte l'app desktop au relais pour recevoir les actions lancées depuis un autre appareil.
   * @returns {Promise<void>}
   */
  async function startDesktopRelayAgent(): Promise<void> {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!isDesktopApp.value || agentEventSource || !token) {
      return
    }
    if (agentReconnectTimer) {
      clearTimeout(agentReconnectTimer)
      agentReconnectTimer = null
    }

    const query = new URLSearchParams({ token })
    try {
      const { getVersion } = await import('@tauri-apps/api/app')
      query.set('app_version', await getVersion())
    } catch {
      // Version inconnue : la présence reste affichée sans elle.
    }
    if (agentEventSource) {
      return
    }

    const apiBase = String(config.public.apiBase || '').replace(/\/$/, '')
    const source = new EventSource(`${apiBase}/desktop-relay/agent/stream?${query.toString()}`)
    agentEventSource = source
    source.onmessage = (event: MessageEvent<string>): void => {
      try {
        handleAgentMessage(JSON.parse(event.data) as DesktopRelayAgentMessage)
      } catch {
        // Trame illisible : ignorée.
      }
    }
    source.onerror = (): void => {
      if (source.readyState !== EventSource.CLOSED) {
        return
      }
      agentEventSource = null
      agentReconnectTimer = setTimeout((): void => {
        startDesktopRelayAgent().catch((): void => {})
      }, RECONNECT_DELAY_MS)
    }
  }

  /**
   * Déconnecte l'app desktop du relais et arrête les flux qu'elle transmettait.
   * @returns {void}
   */
  function stopDesktopRelayAgent(): void {
    if (agentReconnectTimer) {
      clearTimeout(agentReconnectTimer)
      agentReconnectTimer = null
    }
    agentEventSource?.close()
    agentEventSource = null
    for (const stopRelayedStream of [...relayedStreamStoppers.values()]) {
      stopRelayedStream()
    }
  }

  return { startDesktopRelayAgent, stopDesktopRelayAgent }
}
