import type { ComputedRef, Ref } from 'vue'

export type DesktopWorkerName = 'vinted' | 'amazon' | 'cardmarket' | 'leboncoin'

export type DesktopRelayHttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

export type DesktopRelayStreamKind = 'sse' | 'ws'

export type DesktopRelayCommand = {
  worker: DesktopWorkerName
  method: DesktopRelayHttpMethod
  path: string
  body?: unknown
  response_type?: 'json' | 'blob'
  timeout_ms?: number
}

export type DesktopRelayResponse = {
  status: number
  data?: unknown
  content_type?: string | null
  encoding?: 'json' | 'text' | 'base64'
  error?: string | null
}

export type DesktopRelayStreamEvent = {
  data: string
  event?: string
}

export type DesktopRelayStreamHandlers = {
  onEvents: (events: DesktopRelayStreamEvent[]) => void
  onEnd: (error: string | null) => void
}

export type DesktopRelayClientMessage =
  | {
      type: 'agent-status'
      online: boolean
      connected_at?: number
      app_version?: string | null
      relay_instance?: string
    }
  | ({ type: 'response'; id: string } & DesktopRelayResponse)
  | { type: 'stream-events'; id: string; events: DesktopRelayStreamEvent[] }
  | { type: 'stream-end'; id: string; error?: string | null }
  | { type: 'connection-replaced' }

export type DesktopRelayAgentMessage =
  | ({ type: 'request'; id: string } & DesktopRelayCommand)
  | { type: 'stream-open'; id: string; worker: DesktopWorkerName; kind: DesktopRelayStreamKind; path: string }
  | { type: 'stream-close'; id: string }
  | { type: 'connection-replaced' }

export type RelayedRequestMessage = Extract<DesktopRelayAgentMessage, { type: 'request' }>

export type RelayedStreamOpenMessage = Extract<DesktopRelayAgentMessage, { type: 'stream-open' }>

export type DesktopRelayRequest = (command: DesktopRelayCommand) => Promise<DesktopRelayResponse>

export type DesktopRelayStreamOpener = (
  worker: DesktopWorkerName,
  kind: DesktopRelayStreamKind,
  path: string,
  handlers: DesktopRelayStreamHandlers,
) => Promise<() => void>

export type DesktopRelayClient = {
  isDesktopRelayOnline: Ref<boolean>
  hasDesktopRelayStatus: Ref<boolean>
  connectDesktopRelay: () => void
  disconnectDesktopRelay: () => void
  waitForDesktopRelayStatus: () => Promise<boolean>
  waitForDesktopAgentOnline: (timeoutMs: number) => Promise<boolean>
  requestThroughDesktop: DesktopRelayRequest
  openDesktopStream: DesktopRelayStreamOpener
}

export type WorkerEventStream = {
  onopen?: (() => void) | null
  onmessage: ((event: MessageEvent<string>) => void) | null
  onerror: (() => void) | null
  close: () => void
}

export type WorkerProgressChannel = {
  close: () => void
}

export type WorkerSocketOptions = {
  authSubprotocol?: boolean
  openTimeoutMs?: number
}

export type DesktopWorkersAccess = {
  canUseDesktopWorkers: ComputedRef<boolean>
  isDesktopAppUnreachable: ComputedRef<boolean>
  waitForDesktopWorkersAvailability: () => Promise<boolean>
  notifyPcUnreachable: (actionLabel: string) => void
  openWorkerEventStream: (worker: DesktopWorkerName, path: string) => WorkerEventStream
  openWorkerSocketStream: (
    worker: DesktopWorkerName,
    path: string,
    onMessage: (data: string) => void,
    options?: WorkerSocketOptions,
  ) => Promise<WorkerProgressChannel | null>
}

export type DesktopRelayAgent = {
  startDesktopRelayAgent: () => Promise<void>
  stopDesktopRelayAgent: () => void
}

export type RelayedWorkerRoute = {
  method: DesktopRelayHttpMethod
  path: RegExp
}
