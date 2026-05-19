import type { Ref } from 'vue'
import { OPENCV_URL } from '~/composables/useOpenCv'

/**
 * - `idle`      : detector stopped / OpenCV not ready
 * - `watching`  : no card quad locked yet
 * - `settling`  : a card quad is tracked, waiting for it to be held steady
 * - `captured`  : a card was just shot
 * - `cooldown`  : waiting for the card to leave the frame before the next one
 */
export type AutoScanPhase = 'idle' | 'watching' | 'settling' | 'captured' | 'cooldown'

/** A detected card outline, in **video intrinsic pixel** coordinates. */
export type CardQuad = [Pt, Pt, Pt, Pt]
interface Pt {
  x: number
  y: number
}

export interface UseCardAutoScanOptions {
  /** Live preview element frames are sampled from. */
  video: Ref<HTMLVideoElement | null>
  /** Detector only runs while this is `true`. */
  enabled: Ref<boolean>
  /** `true` while an upload is in flight; never capture then. */
  busy: Ref<boolean>
  /** Called once per card with the deskewed, cropped card JPEG. */
  onCapture: (file: File) => void | Promise<void>
}

/** How often we ship a frame to the worker (ms). The heavy work is off-thread. */
const FRAME_MS = 140
/** Long edge of the downscaled frame sent for detection. */
const PROC_EDGE = 480
/** Steady tolerance as a fraction of the frame's long edge. */
const STEADY_FRAC = 0.013
/** Consecutive steady detections before firing (~0.5 s). */
const STEADY_TICKS = 4
/** "No card" detections before re-arming after a shot (card removed). */
const LOST_TICKS_REARM = 3
/** Floor between two captures (anti double-shot). */
const MIN_COOLDOWN_MS = 1500

/**
 * Touch-free card scanner. All OpenCV work (contour detection + perspective
 * crop) runs in a **Web Worker** so the ~9 MB wasm never freezes the phone.
 * The worker streams back the card quad (video-pixel coords) which we expose as
 * `quad` for the tracking outline; once it is held steady we ask the worker to
 * deskew-crop the card and fire `onCapture` **once**. The next shot only arms
 * after the card leaves the frame — no quad ⇒ nothing happens (no spam).
 *
 * @param opts - Video element, enable/busy flags and the capture callback.
 * @returns Reactive `phase`, `quad`, `ready` and `loadError` for the UI.
 */
export function useCardAutoScan(opts: UseCardAutoScanOptions) {
  const { video, enabled, busy, onCapture } = opts

  const phase: Ref<AutoScanPhase> = ref('idle')
  const quad: Ref<CardQuad | null> = ref(null)
  const ready: Ref<boolean> = ref(false)
  const loadError: Ref<string | null> = ref(null)

  let worker: Worker | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let grabCanvas: HTMLCanvasElement | null = null
  let grabCtx: CanvasRenderingContext2D | null = null
  let detectInFlight = false
  let capturing = false

  /**
   * Draw the current video frame into the scratch canvas at `longEdge` and
   * return its transferable RGBA buffer (no `createImageBitmap` — iOS-safe).
   * @param longEdge - Target long-edge size (0 = full intrinsic resolution).
   * @returns The frame buffer + its pixel dimensions, or `null`.
   */
  function grabFrame(longEdge: number): { buf: ArrayBuffer; w: number; h: number } | null {
    const el = video.value
    if (!el || el.readyState < 2 || !el.videoWidth || !el.videoHeight) {
      return null
    }
    const vw = el.videoWidth
    const vh = el.videoHeight
    const scale = longEdge > 0 ? Math.min(1, longEdge / Math.max(vw, vh)) : 1
    const w = Math.max(1, Math.round(vw * scale))
    const h = Math.max(1, Math.round(vh * scale))
    if (!grabCanvas) {
      grabCanvas = document.createElement('canvas')
    }
    if (grabCanvas.width !== w || grabCanvas.height !== h) {
      grabCanvas.width = w
      grabCanvas.height = h
      grabCtx = grabCanvas.getContext('2d', { willReadFrequently: true })
    }
    if (!grabCtx) {
      return null
    }
    grabCtx.drawImage(el, 0, 0, w, h)
    return { buf: grabCtx.getImageData(0, 0, w, h).data.buffer as ArrayBuffer, w, h }
  }
  let lastCorners: Pt[] | null = null
  let steadyTicks = 0
  let lostTicks = 0
  let lastCaptureAt = 0

  /**
   * Mean corner displacement between two ordered quads (video px).
   * @param a - First quad.
   * @param b - Second quad.
   * @returns Average per-corner Euclidean distance.
   */
  function cornerDrift(a: Pt[], b: Pt[]): number {
    let acc = 0
    for (let i = 0; i < 4; i += 1) {
      acc += Math.hypot(a[i]!.x - b[i]!.x, a[i]!.y - b[i]!.y)
    }
    return acc / 4
  }

  /**
   * Apply the steady-then-capture state machine to a fresh detection.
   * @param corners - Ordered card corners in video-intrinsic px, or `null`.
   */
  function onDetection(corners: Pt[] | null): void {
    const el = video.value
    if (!corners || !el) {
      quad.value = null
      lastCorners = null
      steadyTicks = 0
      if (phase.value === 'cooldown') {
        lostTicks += 1
        if (lostTicks >= LOST_TICKS_REARM) {
          phase.value = 'watching'
        }
      } else if (phase.value !== 'idle' && !capturing) {
        phase.value = 'watching'
      }
      return
    }

    quad.value = [corners[0]!, corners[1]!, corners[2]!, corners[3]!]
    lostTicks = 0

    if (phase.value === 'cooldown' || capturing) {
      return
    }

    const longEdge = Math.max(el.videoWidth, el.videoHeight) || 1080
    if (lastCorners && cornerDrift(corners, lastCorners) < longEdge * STEADY_FRAC) {
      steadyTicks += 1
    } else {
      steadyTicks = 0
    }
    lastCorners = corners

    if (steadyTicks < STEADY_TICKS || busy.value || Date.now() - lastCaptureAt < MIN_COOLDOWN_MS) {
      phase.value = 'settling'
      return
    }

    // Steady, fresh card → ask the worker to deskew-crop the full-res frame.
    capturing = true
    steadyTicks = 0
    phase.value = 'captured'
    const full = grabFrame(0)
    if (!worker || !full) {
      capturing = false
      phase.value = 'watching'
      return
    }
    worker.postMessage({ t: 'warp', buf: full.buf, w: full.w, h: full.h, corners }, [full.buf])
  }

  /** Grab one downscaled frame and hand it to the worker for detection. */
  function pumpFrame(): void {
    if (!worker || !enabled.value || detectInFlight || capturing || busy.value) {
      return
    }
    const el = video.value
    if (!el || !el.videoWidth) {
      return
    }
    const f = grabFrame(PROC_EDGE)
    if (!f) {
      return
    }
    detectInFlight = true
    worker.postMessage({ t: 'detect', buf: f.buf, w: f.w, h: f.h, vw: el.videoWidth, vh: el.videoHeight }, [f.buf])
  }

  /**
   * Worker → main messages: readiness, detections and the deskewed crop.
   * @param e - The message event from the detector worker.
   */
  function onWorkerMessage(e: MessageEvent): void {
    const d = e.data as
      | { t: 'ready' }
      | { t: 'error'; m: string }
      | { t: 'quad'; corners: Pt[] }
      | { t: 'nq' }
      | { t: 'warped'; buf: ArrayBuffer; w: number; h: number }
    if (d.t === 'ready') {
      ready.value = true
      phase.value = 'watching'
      if (timer === null) {
        timer = setInterval(pumpFrame, FRAME_MS)
      }
      return
    }
    if (d.t === 'error') {
      loadError.value = d.m
      ready.value = false
      return
    }
    if (d.t === 'quad') {
      detectInFlight = false
      onDetection(d.corners)
      return
    }
    if (d.t === 'nq') {
      detectInFlight = false
      onDetection(null)
      return
    }
    if (d.t === 'warped') {
      lastCaptureAt = Date.now()
      lostTicks = 0
      const finishCooldown = (): void => {
        capturing = false
        phase.value = 'cooldown'
      }
      const cnv = document.createElement('canvas')
      cnv.width = d.w
      cnv.height = d.h
      const c2 = cnv.getContext('2d')
      if (!c2) {
        finishCooldown()
        return
      }
      c2.putImageData(new ImageData(new Uint8ClampedArray(d.buf), d.w, d.h), 0, 0)
      cnv.toBlob(
        (blob) => {
          if (!blob) {
            finishCooldown()
            return
          }
          const file = new File([blob], `card-${Date.now()}.jpg`, { type: 'image/jpeg' })
          void Promise.resolve(onCapture(file)).finally(finishCooldown)
        },
        'image/jpeg',
        0.92,
      )
    }
  }

  /** Spawn the worker and kick off OpenCV loading inside it. */
  function startWorker(): void {
    if (worker || typeof Worker === 'undefined') {
      if (!worker) {
        loadError.value = 'Scan auto non supporté par ce navigateur'
      }
      return
    }
    try {
      worker = new Worker(new URL('../workers/cardDetector.worker.ts', import.meta.url))
    } catch {
      loadError.value = 'Moteur de scan indisponible'
      return
    }
    worker.onmessage = onWorkerMessage
    worker.onerror = (): void => {
      loadError.value = 'Moteur de scan indisponible'
    }
    worker.postMessage({ t: 'init', url: OPENCV_URL })
  }

  /** Tear everything down (disable / unmount). */
  function stopAll(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    if (worker) {
      worker.terminate()
      worker = null
    }
    grabCanvas = null
    grabCtx = null
    detectInFlight = false
    capturing = false
    lastCorners = null
    steadyTicks = 0
    lostTicks = 0
    quad.value = null
    ready.value = false
    phase.value = 'idle'
  }

  watch(
    enabled,
    (on) => {
      if (on) {
        startWorker()
      } else {
        stopAll()
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(stopAll)

  return { phase, quad, ready, loadError }
}
