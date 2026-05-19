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

/** ~10 fps cadence. The worker decides if it can keep up via the in-flight gate. */
const FRAME_MS = 100
/** Long edge of the downscaled frame sent for detection (more = sharper quad). */
const PROC_EDGE = 640
/** Steady tolerance as a fraction of the frame's long edge. */
const STEADY_FRAC = 0.014
/** Consecutive steady detections before firing (~0.4 s @ 100 ms cadence). */
const STEADY_TICKS = 4
/** "No card" detections before re-arming after a shot (card removed). */
const LOST_TICKS_REARM = 3
/** Floor between two captures (anti double-shot). */
const MIN_COOLDOWN_MS = 1500
/** How many shots we take in a burst — we keep the sharpest for OCR. */
const BURST_COUNT = 2
/** Gap between burst shots so focus / exposure has a chance to settle. */
const BURST_INTERVAL_MS = 130
/** Lerp weight (new vs previous) when tracking the displayed quad. */
const SMOOTH_LERP = 0.5
/** Drift above this fraction of the long edge ⇒ new scene, snap instead of lerp. */
const SCENE_CHANGE_FRAC = 0.22
/** Two consecutive detections within this drift = confirmed (kills flicker). */
const VOTE_DRIFT_FRAC = 0.12
/** Empty detections we wait through before the overlay disappears (≈ 400 ms). */
const MISS_LINGER_TICKS = 4
/**
 * Pokémon card ratio — we force the *displayed* rect to this so the overlay
 * always reads as a card even when the underlying detection has slight noise.
 */
const CARD_AR = 1.397

interface BurstShot {
  buf: ArrayBuffer
  w: number
  h: number
  sharpness: number
}

/**
 * Touch-free card scanner. All OpenCV work (contour detection + perspective
 * crop) runs in a Web Worker so the ~9 MB wasm never freezes the phone. The
 * worker streams back the card quad (video-pixel coords) which we **smooth**
 * before exposing as `quad` (the overlay rectangle follows your hand without
 * jitter). Once the quad is held steady, a small **burst of captures** is
 * sent and the **sharpest** one wins — much better OCR results under light
 * hand shake / focus hunt.
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
  let lastCorners: Pt[] | null = null
  let displayedCorners: Pt[] | null = null
  let pendingCorners: Pt[] | null = null
  let missTicks = 0
  let steadyTicks = 0
  let lostTicks = 0
  let lastCaptureAt = 0

  let burstCorners: Pt[] | null = null
  let burstShots: BurstShot[] = []
  let burstAwaiting = 0
  let burstTimer: ReturnType<typeof setTimeout> | null = null

  /**
   * Draw the current video frame into the scratch canvas at `longEdge` and
   * return its transferable RGBA buffer (no `createImageBitmap` — iOS-safe).
   *
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
   * Smooth corner movement so the orange overlay follows the card without
   * jittering on small detection noise — snap on big scene changes.
   *
   * @param prev - Previously displayed corners (or null).
   * @param next - Fresh corners from the worker.
   * @param longEdge - Frame long edge (video px) — used to scale the drift gate.
   * @returns Smoothed corners ready to display.
   */
  function smoothCorners(prev: Pt[] | null, next: Pt[], longEdge: number): Pt[] {
    if (!prev) {
      return next
    }
    if (cornerDrift(prev, next) > longEdge * SCENE_CHANGE_FRAC) {
      return next
    }
    const t = SMOOTH_LERP
    return [0, 1, 2, 3].map((i) => ({
      x: prev[i]!.x * (1 - t) + next[i]!.x * t,
      y: prev[i]!.y * (1 - t) + next[i]!.y * t,
    })) as Pt[]
  }

  /**
   * Force the displayed rectangle to the Pokémon card aspect ratio (88/63),
   * keeping the detected center + rotation. Detections under perspective are
   * always trapezoids with small noise; rendering a forced-ratio rotated
   * rectangle reads as "the card" instead of "some quad" — same trick the
   * competitor uses for that locked-on look.
   *
   * @param q - Smoothed corners (any quadrilateral) in video-intrinsic px.
   * @returns Card-AR rectangle corners at the same center, rotation and scale.
   */
  function forceCardShape(q: Pt[]): Pt[] {
    const cx = (q[0]!.x + q[1]!.x + q[2]!.x + q[3]!.x) / 4
    const cy = (q[0]!.y + q[1]!.y + q[2]!.y + q[3]!.y) / 4
    const topDx = q[1]!.x - q[0]!.x
    const topDy = q[1]!.y - q[0]!.y
    const botDx = q[2]!.x - q[3]!.x
    const botDy = q[2]!.y - q[3]!.y
    const avgW = (Math.hypot(topDx, topDy) + Math.hypot(botDx, botDy)) / 2
    const avgH =
      (Math.hypot(q[3]!.x - q[0]!.x, q[3]!.y - q[0]!.y) + Math.hypot(q[2]!.x - q[1]!.x, q[2]!.y - q[1]!.y)) / 2
    let w: number
    let h: number
    if (avgH >= avgW) {
      w = avgW
      h = avgW * CARD_AR
    } else {
      h = avgH
      w = avgH * CARD_AR
    }
    const angle = Math.atan2((topDy + botDy) / 2, (topDx + botDx) / 2)
    const cos = Math.cos(angle)
    const sin = Math.sin(angle)
    const dx = w / 2
    const dy = h / 2
    const rot = (px: number, py: number): Pt => ({
      x: cx + px * cos - py * sin,
      y: cy + px * sin + py * cos,
    })
    return [rot(-dx, -dy), rot(dx, -dy), rot(dx, dy), rot(-dx, dy)]
  }

  /**
   * Average two equal-length quads corner-by-corner.
   * @param a - First quad.
   * @param b - Second quad.
   * @returns A quad whose corners are the midpoints of `a` and `b`.
   */
  function averageQuad(a: Pt[], b: Pt[]): Pt[] {
    return [0, 1, 2, 3].map((i) => ({
      x: (a[i]!.x + b[i]!.x) / 2,
      y: (a[i]!.y + b[i]!.y) / 2,
    })) as Pt[]
  }

  /** Start a burst: send the first warp request; subsequent ones are scheduled. */
  function beginBurst(corners: Pt[]): void {
    burstCorners = corners
    burstShots = []
    burstAwaiting = BURST_COUNT
    capturing = true
    steadyTicks = 0
    phase.value = 'captured'
    requestWarp()
  }

  /** Send the next warp request from the burst (or finalise if we've collected enough). */
  function requestWarp(): void {
    if (!worker || !burstCorners) {
      finaliseBurst()
      return
    }
    if (burstShots.length >= burstAwaiting) {
      finaliseBurst()
      return
    }
    const full = grabFrame(0)
    if (!full) {
      // Skip this shot but keep trying — maybe the next one lands.
      if (burstShots.length + 1 < burstAwaiting) {
        burstTimer = setTimeout(requestWarp, BURST_INTERVAL_MS)
      } else {
        finaliseBurst()
      }
      return
    }
    worker.postMessage({ t: 'warp', buf: full.buf, w: full.w, h: full.h, corners: burstCorners }, [full.buf])
  }

  /** Pick the sharpest shot from the burst, encode JPEG and hand it to `onCapture`. */
  function finaliseBurst(): void {
    if (burstTimer !== null) {
      clearTimeout(burstTimer)
      burstTimer = null
    }
    if (!burstShots.length) {
      burstCorners = null
      capturing = false
      phase.value = 'cooldown'
      lastCaptureAt = Date.now()
      return
    }
    burstShots.sort((a, b) => b.sharpness - a.sharpness)
    const best = burstShots[0]!
    burstShots = []
    burstCorners = null

    const cnv = document.createElement('canvas')
    cnv.width = best.w
    cnv.height = best.h
    const ctx = cnv.getContext('2d')
    const finishCooldown = (): void => {
      capturing = false
      phase.value = 'cooldown'
    }
    if (!ctx) {
      finishCooldown()
      return
    }
    ctx.putImageData(new ImageData(new Uint8ClampedArray(best.buf), best.w, best.h), 0, 0)
    cnv.toBlob(
      (blob) => {
        if (!blob) {
          finishCooldown()
          return
        }
        const file = new File([blob], `card-${Date.now()}.jpg`, { type: 'image/jpeg' })
        lastCaptureAt = Date.now()
        lostTicks = 0
        void Promise.resolve(onCapture(file)).finally(finishCooldown)
      },
      'image/jpeg',
      0.92,
    )
  }

  /**
   * Apply voting + miss-linger + the steady-then-capture state machine to a
   * fresh detection. Voting (two consecutive consistent detections) and a
   * short linger on empty frames stop the overlay from flickering / morphing
   * on every spurious frame — only confirmed cards reach the display.
   *
   * @param corners - Ordered card corners in video-intrinsic px, or `null`.
   */
  function onDetection(corners: Pt[] | null): void {
    const el = video.value
    if (!el) {
      return
    }
    const longEdge = Math.max(el.videoWidth, el.videoHeight) || 1080

    // No card this tick — linger before clearing so a single bad frame doesn't
    // hide the overlay we are tracking.
    if (!corners) {
      pendingCorners = null
      missTicks += 1
      if (missTicks >= MISS_LINGER_TICKS) {
        lastCorners = null
        displayedCorners = null
        quad.value = null
        steadyTicks = 0
        if (phase.value === 'cooldown') {
          lostTicks += 1
          if (lostTicks >= LOST_TICKS_REARM) {
            phase.value = 'watching'
          }
        } else if (phase.value !== 'idle' && !capturing) {
          phase.value = 'watching'
        }
      }
      return
    }
    missTicks = 0

    // Voting: wait for two consecutive detections within VOTE_DRIFT_FRAC of
    // each other before trusting the result. Hand-shake / texture flicker
    // produces wildly varying quads and gets filtered here.
    if (!pendingCorners) {
      pendingCorners = corners
      return
    }
    if (cornerDrift(corners, pendingCorners) > longEdge * VOTE_DRIFT_FRAC) {
      pendingCorners = corners
      return
    }
    const confirmed = averageQuad(pendingCorners, corners)
    pendingCorners = corners

    // Smooth toward the confirmed quad, then force a card-AR rectangle on top
    // — the displayed rectangle reads as "the card" instead of "some shape".
    displayedCorners = smoothCorners(displayedCorners, confirmed, longEdge)
    const shaped = forceCardShape(displayedCorners)
    quad.value = [shaped[0]!, shaped[1]!, shaped[2]!, shaped[3]!]
    lostTicks = 0

    if (phase.value === 'cooldown' || capturing) {
      return
    }

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

    beginBurst(corners)
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
      | { t: 'warped'; buf: ArrayBuffer; w: number; h: number; sharpness: number }
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
      burstShots.push({ buf: d.buf, w: d.w, h: d.h, sharpness: d.sharpness })
      if (burstShots.length < burstAwaiting) {
        burstTimer = setTimeout(requestWarp, BURST_INTERVAL_MS)
      } else {
        finaliseBurst()
      }
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
    if (burstTimer !== null) {
      clearTimeout(burstTimer)
      burstTimer = null
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
    displayedCorners = null
    pendingCorners = null
    missTicks = 0
    burstCorners = null
    burstShots = []
    burstAwaiting = 0
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
