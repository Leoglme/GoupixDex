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
  let detectInFlight = false
  let capturing = false
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

    // Steady, fresh card → ask the worker to deskew-crop it.
    capturing = true
    steadyTicks = 0
    phase.value = 'captured'
    const w = worker
    if (!w) {
      capturing = false
      return
    }
    createImageBitmap(el)
      .then((bmp) => {
        w.postMessage({ t: 'warp', bmp, vw: el.videoWidth, vh: el.videoHeight, corners }, [bmp])
      })
      .catch(() => {
        capturing = false
        phase.value = 'watching'
      })
  }

  /** Grab one frame and hand it to the worker for detection. */
  function pumpFrame(): void {
    const el = video.value
    if (
      !worker ||
      !enabled.value ||
      detectInFlight ||
      capturing ||
      busy.value ||
      !el ||
      el.readyState < 2 ||
      !el.videoWidth
    ) {
      return
    }
    detectInFlight = true
    createImageBitmap(el)
      .then((bmp) => {
        worker?.postMessage({ t: 'detect', bmp, vw: el.videoWidth, vh: el.videoHeight }, [bmp])
      })
      .catch(() => {
        detectInFlight = false
      })
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
      | { t: 'warped'; buf: ArrayBuffer }
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
      const file = new File([d.buf], `card-${Date.now()}.jpg`, { type: 'image/jpeg' })
      lastCaptureAt = Date.now()
      lostTicks = 0
      void Promise.resolve(onCapture(file)).finally(() => {
        capturing = false
        phase.value = 'cooldown'
      })
    }
  }

  /** Spawn the worker and kick off OpenCV loading inside it. */
  function startWorker(): void {
    if (worker || typeof Worker === 'undefined' || typeof createImageBitmap === 'undefined') {
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
