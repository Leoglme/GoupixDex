import type { ComputedRef } from 'vue'
import type {
  DesktopRelayStreamEvent,
  DesktopWorkerName,
  DesktopWorkersAccess,
  WorkerEventStream,
  WorkerProgressChannel,
  WorkerSocketOptions,
} from '~/types/DesktopRelay'

const TOKEN_KEY: string = 'goupix_token'
const DEFAULT_SOCKET_OPEN_TIMEOUT_MS: number = 8_000
const LOCAL_WORKER_DEFAULT_BASES: Record<DesktopWorkerName, string> = {
  vinted: 'http://127.0.0.1:18766',
  amazon: 'http://127.0.0.1:18768',
  cardmarket: 'http://127.0.0.1:18770',
  leboncoin: 'http://127.0.0.1:18769',
}

/**
 * Donne à un `EventSource` la forme commune aux flux de progression (local, relayé ou API).
 * @param {EventSource} source - Flux SSE ouvert par le navigateur.
 * @returns {WorkerEventStream} Flux qui relaie `onopen`, `onmessage` et `onerror`.
 */
export function wrapEventSource(source: EventSource): WorkerEventStream {
  const stream: WorkerEventStream = { onmessage: null, onerror: null, close: (): void => source.close() }
  source.onopen = (): void => stream.onopen?.()
  source.onmessage = (event: MessageEvent<string>): void => stream.onmessage?.(event)
  source.onerror = (): void => stream.onerror?.()
  return stream
}

/**
 * Actions réservées aux workers du PC : en direct dans l'app desktop, via le relais depuis un autre appareil.
 * @returns {DesktopWorkersAccess} Disponibilité des workers et ouverture de leurs flux de progression.
 */
export function useDesktopWorkers(): DesktopWorkersAccess {
  const config = useRuntimeConfig()
  const { isDesktopApp } = useDesktopRuntime()
  const { isDesktopRelayOnline, hasDesktopRelayStatus, waitForDesktopRelayStatus, openDesktopStream } =
    useDesktopRelay()

  const canUseDesktopWorkers: ComputedRef<boolean> = computed(
    (): boolean => isDesktopApp.value || isDesktopRelayOnline.value,
  )
  // Attend la première présence connue : un bandeau « ouvrez GoupixDex sur votre PC » ne clignote pas au chargement.
  const isDesktopAppUnreachable: ComputedRef<boolean> = computed(
    (): boolean => !isDesktopApp.value && hasDesktopRelayStatus.value && !isDesktopRelayOnline.value,
  )

  /**
   * Attend de savoir si les workers du PC sont joignables (immédiat dans l'app desktop).
   * @returns {Promise<boolean>} True quand une action réservée au desktop peut être lancée.
   */
  async function waitForDesktopWorkersAvailability(): Promise<boolean> {
    if (isDesktopApp.value) {
      return true
    }
    await waitForDesktopRelayStatus()
    return isDesktopRelayOnline.value
  }

  /**
   * Adresse locale d'un worker (config Nuxt, sinon port par défaut).
   * @param {DesktopWorkerName} worker - Worker visé.
   * @returns {string} Base HTTP sans slash final.
   */
  function localWorkerBase(worker: DesktopWorkerName): string {
    const configuredBases: Record<DesktopWorkerName, unknown> = {
      vinted: config.public.vintedLocalBase,
      amazon: config.public.amazonLocalBase,
      cardmarket: config.public.cardmarketLocalBase,
      leboncoin: config.public.leboncoinLocalBase,
    }
    return String(configuredBases[worker] || LOCAL_WORKER_DEFAULT_BASES[worker]).replace(/\/$/, '')
  }

  /**
   * Ajoute au chemin d'un flux local le JWT et l'API distante attendus par les workers.
   * @param {string} path - Chemin du flux sur le worker.
   * @param {boolean} includeToken - False quand le JWT part en sous-protocole WebSocket.
   * @returns {string} Chemin complété de sa query string.
   */
  function withLocalWorkerAuth(path: string, includeToken: boolean): string {
    const query = new URLSearchParams()
    const token = localStorage.getItem(TOKEN_KEY)
    if (includeToken && token) {
      query.set('token', token)
    }
    query.set('remote_api', String(config.public.apiBase || '').replace(/\/$/, ''))
    return `${path}${path.includes('?') ? '&' : '?'}${query.toString()}`
  }

  /**
   * Ouvre un flux SSE de progression d'un worker, en local sur le PC ou via le relais.
   * @param {DesktopWorkerName} worker - Worker qui publie la progression.
   * @param {string} path - Chemin du flux sur le worker (`/articles/12/listing-progress`…).
   * @returns {WorkerEventStream} Flux au format `EventSource` (`onmessage`, `onerror`, `close`).
   */
  function openWorkerEventStream(worker: DesktopWorkerName, path: string): WorkerEventStream {
    if (isDesktopApp.value) {
      return wrapEventSource(new EventSource(`${localWorkerBase(worker)}${withLocalWorkerAuth(path, true)}`))
    }

    const stream: WorkerEventStream = { onmessage: null, onerror: null, close: (): void => {} }
    let isClosed = false
    let stopRelayStream: () => void = (): void => {}
    stream.close = (): void => {
      isClosed = true
      stopRelayStream()
    }
    openDesktopStream(worker, 'sse', path, {
      onEvents: (events: DesktopRelayStreamEvent[]): void => {
        for (const event of events) {
          if (isClosed) {
            return
          }
          stream.onmessage?.(new MessageEvent('message', { data: event.data }))
        }
      },
      onEnd: (): void => {
        if (!isClosed) {
          stream.onerror?.()
        }
      },
    }).then((stop: () => void): void => {
      stopRelayStream = stop
      if (isClosed) {
        stop()
      }
    })
    return stream
  }

  /**
   * Ouvre un WebSocket de progression d'un worker (local ou relayé) et attend son ouverture.
   * @param {DesktopWorkerName} worker - Worker qui publie la progression.
   * @param {string} path - Chemin du WebSocket sur le worker (`/ws/progress`…).
   * @param {(data: string) => void} onMessage - Reçoit chaque trame brute.
   * @param {WorkerSocketOptions} options - `authSubprotocol` pour passer le JWT hors de l'URL, délai d'ouverture.
   * @returns {Promise<WorkerProgressChannel | null>} Canal ouvert, ou null si le worker ne répond pas.
   */
  async function openWorkerSocketStream(
    worker: DesktopWorkerName,
    path: string,
    onMessage: (data: string) => void,
    options: WorkerSocketOptions = {},
  ): Promise<WorkerProgressChannel | null> {
    if (isDesktopApp.value) {
      const token = localStorage.getItem(TOKEN_KEY)
      const socketBase = localWorkerBase(worker).replace(/^http/i, (scheme: string): string =>
        scheme.toLowerCase() === 'https' ? 'wss' : 'ws',
      )
      const protocols = options.authSubprotocol && token ? [`goupix-jwt.${token.trim()}`] : undefined
      const socket = new WebSocket(`${socketBase}${withLocalWorkerAuth(path, !options.authSubprotocol)}`, protocols)
      socket.onmessage = (event: MessageEvent): void => onMessage(String(event.data))
      const isOpened = await new Promise<boolean>((resolve: (value: boolean) => void): void => {
        const timer = setTimeout((): void => resolve(false), options.openTimeoutMs ?? DEFAULT_SOCKET_OPEN_TIMEOUT_MS)
        socket.onopen = (): void => {
          clearTimeout(timer)
          resolve(true)
        }
        socket.onerror = (): void => {
          clearTimeout(timer)
          resolve(false)
        }
      })
      if (!isOpened) {
        socket.close()
        return null
      }
      return { close: (): void => socket.close() }
    }

    let isClosed = false
    let hasFailedToOpen = false
    const stopRelayStream = await openDesktopStream(worker, 'ws', path, {
      onEvents: (events: DesktopRelayStreamEvent[]): void => {
        for (const event of events) {
          if (!isClosed) {
            onMessage(event.data)
          }
        }
      },
      onEnd: (error: string | null): void => {
        hasFailedToOpen = hasFailedToOpen || Boolean(error)
      },
    })
    if (hasFailedToOpen) {
      return null
    }
    return {
      close: (): void => {
        isClosed = true
        stopRelayStream()
      },
    }
  }

  return {
    canUseDesktopWorkers,
    isDesktopAppUnreachable,
    waitForDesktopWorkersAvailability,
    openWorkerEventStream,
    openWorkerSocketStream,
  }
}
