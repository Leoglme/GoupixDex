import type { Ref } from 'vue'
import type { AxiosInstance } from 'axios'
import type { CollectionCard } from '~/composables/useCollection'

/**
 * Phase of a scan event in the real-time pipeline.
 * - `queued`        : the phone upload reached the server, work hasn't started
 * - `ocr_running`   : Groq vision call in flight
 * - `ocr_done`      : OCR returned; we have a `set_code` + `card_number` guess
 * - `needs_review`  : TCGdex lookup failed, the user has to identify the card manually
 * - `added`         : a `CollectionCard` row exists (created or quantity incremented)
 * - `failed`        : unrecoverable error (OCR crash, DB error, ...)
 */
export type ScanEventStatus = 'queued' | 'ocr_running' | 'ocr_done' | 'needs_review' | 'added' | 'failed'

export interface ScanEvent {
  event_id: string
  user_id: number
  status: ScanEventStatus
  physical_language: string
  image_preview_data_url: string | null
  ocr: Record<string, unknown> | null
  tcgdex_card_id: string | null
  collection_card: CollectionCard | null
  created: boolean | null
  error: string | null
  ts: number
}

interface RecentResponse {
  items: ScanEvent[]
}

interface UploadResponse {
  event_id: string
  status: 'queued'
  physical_language: string
}

/**
 * Most-recent-first ordered list of unique scan events, keyed by `event_id`.
 * @param list - Current event list.
 * @param next - Event payload to insert or merge.
 * @returns {ScanEvent[]} New array containing `next` at the head when unknown, else patched in place.
 */
function upsertEvent(list: ScanEvent[], next: ScanEvent): ScanEvent[] {
  const ix = list.findIndex((e) => e.event_id === next.event_id)
  if (ix === -1) {
    return [next, ...list]
  }
  const out = list.slice()
  out[ix] = { ...out[ix], ...next }
  return out
}

export interface ScanUploadCompressOptions {
  maxEdge?: number
  quality?: number
  mime?: 'image/jpeg' | 'image/webp'
}

/**
 * Resize / re-encode a phone photo client-side before upload.
 *
 * A 12 MP iPhone JPEG (~4 MB) becomes a 1280-px-long-edge JPEG (~200 kB),
 * cutting the upload from ~6 s to ~0.5 s on 4G. We keep the original when
 * we can't decode it (e.g. HEIC on a non-Safari browser).
 *
 * @param file - Source file from `<input type="file">`.
 * @param opts - Long-edge cap (`maxEdge`, default 1280) and JPEG `quality` (default 0.72).
 * @returns {Promise<File>} Compressed file (same name, new mime / size) or the input untouched.
 */
async function compressImageForUpload(file: File, opts: ScanUploadCompressOptions = {}): Promise<File> {
  if (!import.meta.client) {
    return file
  }
  const maxEdge = opts.maxEdge ?? 1280
  const quality = opts.quality ?? 0.72
  const targetMime = opts.mime ?? 'image/jpeg'

  if (typeof createImageBitmap !== 'function' || typeof OffscreenCanvas !== 'function') {
    return file
  }

  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    return file
  }

  const { width, height } = bitmap
  if (!width || !height) {
    bitmap.close?.()
    return file
  }
  const scale = Math.min(1, maxEdge / Math.max(width, height))
  const targetWidth = Math.max(1, Math.round(width * scale))
  const targetHeight = Math.max(1, Math.round(height * scale))

  const canvas = new OffscreenCanvas(targetWidth, targetHeight)
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    bitmap.close?.()
    return file
  }
  ctx.drawImage(bitmap, 0, 0, targetWidth, targetHeight)
  bitmap.close?.()

  let blob: Blob
  try {
    blob = await canvas.convertToBlob({ type: targetMime, quality })
  } catch {
    return file
  }
  const ext = targetMime === 'image/webp' ? 'webp' : 'jpg'
  const baseName = file.name.replace(/\.[^.]+$/, '') || 'scan'
  return new File([blob], `${baseName}.${ext}`, { type: targetMime })
}

/**
 * Build the full WebSocket URL for `/ws/scan-stream` (JWT in `?token=`).
 *
 * @returns URL string, or `null` when run server-side / unauthenticated.
 */
export function buildScanStreamWebSocketUrl(): string | null {
  if (!import.meta.client) {
    return null
  }
  const token = localStorage.getItem('goupix_token')
  if (!token?.trim()) {
    return null
  }
  const config = useRuntimeConfig()
  const base = String(config.public.apiBase || '').replace(/\/$/, '')
  if (!base) {
    return null
  }
  const wsBase = base.replace(/^http/i, (m) => (m.toLowerCase() === 'https' ? 'wss' : 'ws'))
  const qs = new URLSearchParams({ token: token.trim() })
  return `${wsBase}/ws/scan-stream?${qs.toString()}`
}

const POLL_INTERVAL_MS = 2_500
const WS_GIVE_UP_AFTER_RETRIES = 4

/**
 * Real-time scan stream: phone uploads + WebSocket fan-out to every tab of the
 * same authenticated user. Manages reconnect with exponential backoff, replays
 * the server backlog on (re)connect, and de-duplicates events by `event_id`.
 *
 * @returns Reactive `events`, plus `uploadPhoto`, `connect`, `disconnect`, `refreshRecent`.
 */
export function useScanStream() {
  const { $api } = useNuxtApp() as unknown as { $api: AxiosInstance }

  const events: Ref<ScanEvent[]> = ref([])
  const connected: Ref<boolean> = ref(false)
  const connecting: Ref<boolean> = ref(false)
  /** `websocket` when the live socket is up; `polling` when we fall back to HTTP refresh. */
  const connectionMode: Ref<'websocket' | 'polling' | 'offline'> = ref('offline')
  const lastError: Ref<string | null> = ref(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let retries = 0
  let manualClose = false
  let pollingActive = false

  /**
   *
   */
  function pushEvent(ev: ScanEvent): void {
    events.value = upsertEvent(events.value, ev)
  }

  /**
   *
   */
  function clearReconnect(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  /**
   *
   */
  function stopPolling(): void {
    pollingActive = false
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  /** HTTP fallback when WebSocket is unavailable (nginx 404, API pas à jour, etc.). */
  function startPolling(): void {
    if (pollingActive || manualClose) {
      return
    }
    pollingActive = true
    connectionMode.value = 'polling'
    connected.value = true
    connecting.value = false
    lastError.value = null

    const tick = (): void => {
      void refreshRecent(50)
    }
    tick()
    pollTimer = setInterval(tick, POLL_INTERVAL_MS)
  }

  /**
   *
   */
  function scheduleReconnect(): void {
    if (manualClose) {
      return
    }
    if (!pollingActive) {
      startPolling()
    }
    clearReconnect()
    if (retries >= WS_GIVE_UP_AFTER_RETRIES) {
      return
    }
    const delayMs = Math.min(15_000, 800 * 2 ** retries)
    retries += 1
    reconnectTimer = setTimeout(() => {
      void openSocket()
    }, delayMs)
  }

  /**
   *
   */
  async function openSocket(): Promise<void> {
    if (!import.meta.client) {
      return
    }
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
      return
    }
    const url = buildScanStreamWebSocketUrl()
    if (!url) {
      if (!pollingActive) {
        lastError.value = 'Session expirée — reconnectez-vous pour utiliser le scan en direct.'
      }
      return
    }

    connecting.value = true
    manualClose = false
    let next: WebSocket
    try {
      next = new WebSocket(url)
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : 'WebSocket indisponible'
      connecting.value = false
      scheduleReconnect()
      return
    }
    ws = next

    next.onopen = (): void => {
      retries = 0
      connecting.value = false
      connected.value = true
      connectionMode.value = 'websocket'
      lastError.value = null
      stopPolling()
    }
    next.onmessage = (ev: MessageEvent): void => {
      try {
        const payload = JSON.parse(String(ev.data)) as ScanEvent
        if (payload && typeof payload.event_id === 'string') {
          pushEvent(payload)
        }
      } catch {
        /* ignore malformed frames */
      }
    }
    next.onerror = (): void => {
      /* Polling keeps the UI live; WS errors are non-blocking. */
    }
    next.onclose = (): void => {
      ws = null
      if (manualClose) {
        connected.value = false
        connecting.value = false
        connectionMode.value = 'offline'
        return
      }
      connecting.value = false
      if (connectionMode.value === 'websocket') {
        connected.value = false
      }
      scheduleReconnect()
    }
  }

  /**
   * Start live updates: HTTP polling immediately (like eBay sold-top), then try
   * WebSocket when the API route is deployed. No nginx change required.
   *
   * @returns {Promise<void>} Resolves once polling + WS attempt are in flight.
   */
  async function connect(): Promise<void> {
    manualClose = false
    retries = 0
    startPolling()
    await openSocket()
  }

  /**
   * Close the WebSocket and cancel any pending reconnect. Useful in `onBeforeUnmount`.
   *
   * @returns {void} Nothing.
   */
  function disconnect(): void {
    manualClose = true
    clearReconnect()
    stopPolling()
    if (ws) {
      try {
        ws.close()
      } catch {
        /* ignore */
      }
    }
    ws = null
    connected.value = false
    connecting.value = false
    connectionMode.value = 'offline'
  }

  /**
   * Hydrate `events` with the last batch the server kept in memory for this user.
   * Pages call this on mount so users see history before any new scan lands.
   *
   * @param limit - Max events fetched (server caps at 100, default 50).
   * @returns {Promise<void>} Resolves once `events` is populated.
   */
  async function refreshRecent(limit = 50): Promise<void> {
    try {
      const { data } = await $api.get<RecentResponse>('/scan-stream/recent', {
        params: { limit },
      })
      const map = new Map<string, ScanEvent>()
      for (const ev of data.items) {
        map.set(ev.event_id, ev)
      }
      for (const ev of events.value) {
        if (!map.has(ev.event_id)) {
          map.set(ev.event_id, ev)
        }
      }
      // Most-recent first in the UI
      events.value = Array.from(map.values()).sort((a, b) => b.ts - a.ts)
      if (pollingActive) {
        connected.value = true
        lastError.value = null
      }
    } catch (e) {
      if (pollingActive) {
        connected.value = false
        connectionMode.value = 'offline'
      }
      lastError.value = apiErrorMessage(e)
    }
  }

  /**
   * Compress (if possible) and POST a card photo. The phone fires-and-forgets:
   * the desktop receives the matching `event_id` events over the WebSocket as
   * the pipeline progresses.
   *
   * @param file - Photo from `<input type="file">` (camera capture).
   * @param language - Physical language of the card (`fr` | `en` | `ja`).
   * @param hint - Optional OCR hint forwarded server-side (default empty).
   * @param compressOpts - Optional resize / quality overrides (e.g. higher `maxEdge` for webcam).
   * @returns {Promise<UploadResponse>} `{ event_id, status: 'queued' }`.
   */
  async function uploadPhoto(
    file: File,
    language: string,
    hint?: string,
    compressOpts?: ScanUploadCompressOptions,
  ): Promise<UploadResponse> {
    const optimised = await compressImageForUpload(file, compressOpts ?? {})
    const fd = new FormData()
    fd.append('file', optimised)
    fd.append('language', language)
    if (hint?.trim()) {
      fd.append('hint', hint.trim())
    }
    const { data } = await $api.post<UploadResponse>('/scan-stream/photo', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60_000,
    })
    if (pollingActive || connectionMode.value !== 'websocket') {
      window.setTimeout(() => {
        void refreshRecent(50)
      }, 400)
    }
    return data
  }

  return {
    events,
    connected,
    connecting,
    connectionMode,
    lastError,
    connect,
    disconnect,
    refreshRecent,
    uploadPhoto,
  }
}
