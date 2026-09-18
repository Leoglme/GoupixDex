import type { ComputedRef, Ref } from 'vue'
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
  video: Ref<HTMLVideoElement | null> | ComputedRef<HTMLVideoElement | null>
  /** Detector only runs while this is `true`. */
  enabled: Ref<boolean> | ComputedRef<boolean>
  /** `true` while an upload is in flight; never capture then. */
  busy: Ref<boolean>
  /**
   * Called once per card with the deskewed, cropped card JPEG and the raw
   * visual-match candidates (flat `[indexEntry, distance]` pairs from the
   * worker, best first — empty when no index is loaded).
   */
  onCapture: (file: File, matches: number[]) => void | Promise<void>
  /**
   * Live identification: candidates computed on a detection frame (quad or
   * central guide crop), before any capture. Return `true` when the card was
   * committed — the scanner then enters its "remove the card" cooldown; on
   * `false` the miss counts toward the photo-OCR fallback.
   */
  onLiveMatches?: (matches: number[]) => boolean
  /** Called when a burst came out motion-blurred and is being retried — UI hint. */
  onBlurryRetry?: () => void
}

/** ~12 fps cadence. The worker decides if it can keep up via the in-flight gate. */
const FRAME_MS = 80
/** Long edge of the downscaled frame sent for detection (more = sharper quad). */
const PROC_EDGE = 640
/**
 * Long edge of the frame used for the capture warp. The deskewed card is only
 * 630×880 — a 1920 source is plenty for OCR, and grabbing the raw 4K stream
 * here used to allocate ~33 MB per shot (freezes + crashes on phones).
 */
const CAPTURE_EDGE = 1920
/** Floor between two captures (safety net on top of the re-arm gate). */
const MIN_COOLDOWN_MS = 450
/**
 * Empty detection ticks required after a capture before the next card can
 * fire. Two frames (~160 ms) was far too short: a flickering contour made
 * the scanner re-arm while the same card was still in frame → spam.
 */
const CLEAR_TICKS_TO_REARM = 10
/** Minimum quiet time after a commit before re-arming (ms). */
const MIN_REARM_MS = 900
/** Fraction of the frame height covered by the on-screen guide silhouette. */
const GUIDE_HEIGHT_FRAC = 0.62
/** How many shots we take in a burst — we keep the sharpest for OCR. */
const BURST_COUNT = 3
/** Gap between burst shots — wide enough for hand movement to expose new info. */
const BURST_INTERVAL_MS = 160
/** Hard cap on a burst's lifetime; a stuck worker must never freeze the scanner. */
const BURST_WATCHDOG_MS = BURST_COUNT * BURST_INTERVAL_MS + 2500
/**
 * Variance-of-Laplacian floor under which the whole burst counts as
 * motion-blurred. A blurred capture is what turned every scan into
 * « À vérifier »: Groq misreads the set code / collector number on soft
 * pixels. Below this floor the burst is retried on fresh frames instead of
 * uploading garbage. Calibrated on warped 630×880 crops of real card scans:
 * crisp shots land 13-23, a ~1.5 px motion blur ~7, a ~2 px blur ~4 (OCR
 * starts failing) and a ~3 px blur ~2.7 (unreadable).
 */
const MIN_SHARPNESS = 3.0
/** Blurry-burst retries while the card stays in frame (adds ~0.5 s each). */
const MAX_BLUR_RETRIES = 2
/**
 * Live identification attempts that must MISS before the photo-OCR fallback
 * fires. At ~5 attempts/s this gives the on-device index ≈ 0.5 s; unmatched
 * cards (sets without TCGdex images, e.g. JA s8b) then go to OCR.
 */
const LIVE_MATCH_MISSES_BEFORE_PHOTO = 2
/** A detect round-trip longer than this counts as lost (worker hiccup). */
const DETECT_TIMEOUT_MS = 2000
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
  matches: number[]
}

/**
 * Touch-free card scanner. All OpenCV work (contour detection + perspective
 * crop) runs in a Web Worker so the ~9 MB wasm never freezes the phone. The
 * worker streams back the card quad (video-pixel coords) which we **smooth**
 * before exposing as `quad` (the overlay rectangle follows your hand without
 * jitter). Once a card is confirmed, a small **burst of captures** is sent and
 * the **sharpest** one wins; the scanner then waits for the card to leave the
 * frame before re-arming — pass a card, beep, next card.
 *
 * @param opts - Video element, enable/busy flags and the capture callback.
 * @returns Reactive `phase`, `quad`, `ready` and `loadError` for the UI.
 */
export function useCardAutoScan(opts: UseCardAutoScanOptions) {
  const { video, enabled, busy, onCapture, onLiveMatches, onBlurryRetry } = opts

  const phase: Ref<AutoScanPhase> = ref('idle')
  const quad: Ref<CardQuad | null> = ref(null)
  const ready: Ref<boolean> = ref(false)
  const loadError: Ref<string | null> = ref(null)
  /** `true` once the worker holds the visual-match index (instant identification). */
  const matchIndexReady: Ref<boolean> = ref(false)
  let pendingIndexBuffer: ArrayBuffer | null = null

  let worker: Worker | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  // Two dedicated canvases: resizing one shared canvas between the 640 px
  // detection grabs and the full-size capture grabs reallocated its backing
  // store several times per second.
  let detectCanvas: HTMLCanvasElement | null = null
  let detectCtx: CanvasRenderingContext2D | null = null
  let captureCanvas: HTMLCanvasElement | null = null
  let captureCtx: CanvasRenderingContext2D | null = null

  let detectInFlight = false
  let detectSentAt = 0
  let capturing = false
  /** False right after a capture — set back to true once the frame is clear. */
  let armed = true
  let clearTicks = 0
  let lastCorners: Pt[] | null = null
  let displayedCorners: Pt[] | null = null
  let pendingCorners: Pt[] | null = null
  let missTicks = 0
  let lastCaptureAt = 0

  let burstCorners: Pt[] | null = null
  let burstShots: BurstShot[] = []
  let burstMisses = 0
  let burstTimer: ReturnType<typeof setTimeout> | null = null
  let burstWatchdog: ReturnType<typeof setTimeout> | null = null
  let blurRetries = 0
  let liveMatchMisses = 0

  /**
   * Draw the current video frame into the right scratch canvas and return its
   * transferable RGBA buffer (no `createImageBitmap` — iOS-safe).
   *
   * @param longEdge - Target long-edge size.
   * @param forCapture - Use the capture canvas (full quality) instead of the detection one.
   * @returns The frame buffer + its pixel dimensions, or `null`.
   */
  function grabFrame(longEdge: number, forCapture: boolean = false): { buf: ArrayBuffer; w: number; h: number } | null {
    const el = video.value
    if (!el || el.readyState < 2 || !el.videoWidth || !el.videoHeight) {
      return null
    }
    const vw = el.videoWidth
    const vh = el.videoHeight
    const scale = Math.min(1, longEdge / Math.max(vw, vh))
    const w = Math.max(1, Math.round(vw * scale))
    const h = Math.max(1, Math.round(vh * scale))
    let canvas = forCapture ? captureCanvas : detectCanvas
    let ctx = forCapture ? captureCtx : detectCtx
    if (!canvas) {
      canvas = document.createElement('canvas')
      if (forCapture) {
        captureCanvas = canvas
      } else {
        detectCanvas = canvas
      }
    }
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      ctx = canvas.getContext('2d', { willReadFrequently: true })
      if (forCapture) {
        captureCtx = ctx
      } else {
        detectCtx = ctx
      }
    }
    if (!ctx) {
      return null
    }
    ctx.drawImage(el, 0, 0, w, h)
    return { buf: ctx.getImageData(0, 0, w, h).data.buffer as ArrayBuffer, w, h }
  }

  /**
   * Fixed guide rectangle in video-intrinsic px — same geometry as the on-screen
   * silhouette and the worker's central crop. Used for OCR capture when contour
   * detection fails (wood table, sleeve glare…).
   */
  function guideCorners(vw: number, vh: number): Pt[] {
    const gh = vh * GUIDE_HEIGHT_FRAC
    const gw = Math.min(vw * 0.92, (gh * 63) / 88)
    const x = (vw - gw) / 2
    const y = (vh - gh) / 2
    return [
      { x, y },
      { x: x + gw, y },
      { x: x + gw, y: y + gh },
      { x, y: y + gh },
    ]
  }

  /**
   * True when the scanner may fire a photo-OCR burst.
   * @param requireLiveMisses - When true (guide-only path), live hash misses are mandatory even without an index.
   */
  function shouldTriggerPhotoFallback(requireLiveMisses: boolean = false): boolean {
    if (capturing || !armed || busy.value) {
      return false
    }
    if (Date.now() - lastCaptureAt < MIN_COOLDOWN_MS) {
      return false
    }
    if (requireLiveMisses || matchIndexReady.value) {
      return liveMatchMisses >= LIVE_MATCH_MISSES_BEFORE_PHOTO
    }
    return true
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
   * rectangle reads as "the card" instead of "some quad".
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
    burstMisses = 0
    blurRetries = 0
    capturing = true
    phase.value = 'captured'
    if (burstWatchdog !== null) {
      clearTimeout(burstWatchdog)
    }
    // Whatever happens to the worker, the scanner must re-arm itself.
    burstWatchdog = setTimeout(finaliseBurst, BURST_WATCHDOG_MS)
    requestWarp()
  }

  /** Send the next warp request from the burst (or finalise if we've collected enough). */
  function requestWarp(): void {
    if (!capturing) {
      return
    }
    if (!worker || burstShots.length + burstMisses >= BURST_COUNT) {
      finaliseBurst()
      return
    }
    // Use the freshest detected corners so a pivot/move during the burst still
    // yields a correctly cropped card. Fall back to the trigger corners if the
    // detector hasn't returned a new quad yet.
    const corners = lastCorners ?? burstCorners
    const full = grabFrame(CAPTURE_EDGE, true)
    if (!corners || !full) {
      onBurstShotMissed()
      return
    }
    // Corners are in video-intrinsic coords; scale them to the capture frame.
    const el = video.value
    const scale = el && el.videoWidth ? full.w / el.videoWidth : 1
    const scaled = corners.map((p) => ({ x: p.x * scale, y: p.y * scale }))
    worker.postMessage({ t: 'warp', buf: full.buf, w: full.w, h: full.h, corners: scaled }, [full.buf])
  }

  /** One burst shot could not be produced — count it and keep the burst going. */
  function onBurstShotMissed(): void {
    burstMisses += 1
    if (burstShots.length + burstMisses >= BURST_COUNT) {
      finaliseBurst()
    } else {
      burstTimer = setTimeout(requestWarp, BURST_INTERVAL_MS)
    }
  }

  /** Pick the sharpest shot from the burst, encode JPEG and hand it to `onCapture`. */
  function finaliseBurst(): void {
    if (!capturing) {
      return
    }
    if (burstTimer !== null) {
      clearTimeout(burstTimer)
      burstTimer = null
    }
    if (burstWatchdog !== null) {
      clearTimeout(burstWatchdog)
      burstWatchdog = null
    }
    // Every exit path below goes through this: re-arm only after the card
    // leaves the frame (cash-register rhythm), never mid-frame.
    const finishCooldown = (): void => {
      capturing = false
      armed = false
      clearTicks = 0
      lastCaptureAt = Date.now()
      phase.value = 'cooldown'
    }
    if (!burstShots.length) {
      burstCorners = null
      finishCooldown()
      return
    }
    burstShots.sort((a, b) => b.sharpness - a.sharpness)
    const best = burstShots[0]!

    // Motion-blur gate: a soft capture is what turns every scan into
    // « À vérifier » server-side. While the card is still tracked, retry the
    // whole burst on fresh frames instead of uploading it. After the retries
    // the best shot is sent anyway — the server gate + OCR enhancer get their
    // chance, and the user never sees a silent no-op for a card that beeped.
    if (best.sharpness < MIN_SHARPNESS && blurRetries < MAX_BLUR_RETRIES && lastCorners) {
      blurRetries += 1
      burstShots = []
      burstMisses = 0
      burstCorners = lastCorners
      onBlurryRetry?.()
      burstWatchdog = setTimeout(finaliseBurst, BURST_WATCHDOG_MS)
      burstTimer = setTimeout(requestWarp, BURST_INTERVAL_MS)
      return
    }

    burstShots = []
    burstCorners = null

    const cnv = document.createElement('canvas')
    cnv.width = best.w
    cnv.height = best.h
    const ctx = cnv.getContext('2d')
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
        void Promise.resolve(onCapture(file, best.matches)).finally(finishCooldown)
      },
      'image/jpeg',
      0.92,
    )
  }

  /**
   * Apply voting + miss-linger + the capture / re-arm state machine to a fresh
   * detection. Voting (two consecutive consistent detections) and a short
   * linger on empty frames stop the overlay from flickering on every spurious
   * frame — only confirmed cards reach the display.
   *
   * @param corners - Ordered card corners in video-intrinsic px, or `null`.
   */
  function onDetection(corners: Pt[] | null): void {
    const el = video.value
    if (!el) {
      return
    }
    const longEdge = Math.max(el.videoWidth, el.videoHeight) || 1080

    // No card this tick — re-arm only after sustained absence + minimum quiet time.
    if (!corners) {
      pendingCorners = null
      missTicks += 1
      if (!armed) {
        if (Date.now() - lastCaptureAt >= MIN_REARM_MS) {
          clearTicks += 1
          if (clearTicks >= CLEAR_TICKS_TO_REARM) {
            armed = true
            liveMatchMisses = 0
            if (!capturing) {
              phase.value = 'watching'
            }
          }
        }
      } else if (shouldTriggerPhotoFallback(true) && el.videoWidth) {
        // Contour failed but the guide crop had live misses → OCR on the guide zone.
        beginBurst(guideCorners(el.videoWidth, el.videoHeight))
        return
      }
      if (missTicks >= MISS_LINGER_TICKS) {
        lastCorners = null
        displayedCorners = null
        quad.value = null
        if (armed) {
          liveMatchMisses = 0
        }
        if (phase.value !== 'idle' && !capturing && armed) {
          phase.value = 'watching'
        }
      }
      return
    }
    missTicks = 0
    clearTicks = 0

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

    lastCorners = corners

    if (capturing) {
      return
    }

    // Not re-armed yet: the previous card is still in frame. The UI shows
    // "Retirez la carte" — and that label is now actually true.
    if (!armed) {
      phase.value = 'cooldown'
      return
    }

    if (!shouldTriggerPhotoFallback()) {
      return
    }

    // Prefer the fixed guide crop for OCR — contour quads jitter on wood / sleeves.
    const burstCorners = el.videoWidth && matchIndexReady.value ? guideCorners(el.videoWidth, el.videoHeight) : corners
    beginBurst(burstCorners)
  }

  /**
   * Grab one downscaled frame and hand it to the worker for detection. Note we
   * intentionally keep running during a capture burst so `lastCorners` stays
   * fresh — each burst shot uses the latest detection, supporting movement.
   */
  function pumpFrame(): void {
    if (!worker || !enabled.value || busy.value) {
      return
    }
    if (detectInFlight) {
      // A worker hiccup must not kill the loop forever.
      if (Date.now() - detectSentAt > DETECT_TIMEOUT_MS) {
        detectInFlight = false
      } else {
        return
      }
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
    detectSentAt = Date.now()
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
      | { t: 'quad'; corners: Pt[]; matches?: number[] }
      | { t: 'nq'; matches?: number[] }
      | { t: 'warped'; buf: ArrayBuffer; w: number; h: number; sharpness: number; matches?: number[] }
      | { t: 'warp_failed'; m: string }
      | { t: 'index_ready'; count: number }
    if (d.t === 'ready') {
      ready.value = true
      loadError.value = null
      if (pendingIndexBuffer) {
        worker?.postMessage({ t: 'index', buf: pendingIndexBuffer })
      }
      if (enabled.value) {
        phase.value = 'watching'
        startPump()
      }
      return
    }
    if (d.t === 'index_ready') {
      matchIndexReady.value = d.count > 0
      return
    }
    if (d.t === 'error') {
      // Fatal engine failure (OpenCV never loaded / crashed). Reset every
      // transient flag so a later retry starts clean instead of deadlocking.
      loadError.value = d.m
      ready.value = false
      detectInFlight = false
      if (capturing) {
        finaliseBurst()
      }
      return
    }
    if (d.t === 'quad') {
      detectInFlight = false
      handleLiveMatches(d.matches)
      onDetection(d.corners)
      return
    }
    if (d.t === 'nq') {
      detectInFlight = false
      handleLiveMatches(d.matches)
      onDetection(null)
      return
    }
    if (d.t === 'warp_failed') {
      // Non-fatal: skip this shot, the burst keeps going.
      if (capturing) {
        onBurstShotMissed()
      }
      return
    }
    if (d.t === 'warped') {
      if (!capturing) {
        return
      }
      burstShots.push({ buf: d.buf, w: d.w, h: d.h, sharpness: d.sharpness, matches: d.matches ?? [] })
      if (burstShots.length + burstMisses < BURST_COUNT) {
        burstTimer = setTimeout(requestWarp, BURST_INTERVAL_MS)
      } else {
        finaliseBurst()
      }
    }
  }

  /**
   * Forward live identification candidates to the page. A committed card
   * flips the scanner straight into the "remove the card" cooldown; a miss
   * counts toward the photo-OCR fallback trigger.
   * @param matches - Flat `[indexEntry, distance]` pairs from the worker, or `undefined`.
   */
  function handleLiveMatches(matches: number[] | undefined): void {
    if (!matches || !onLiveMatches || !armed || capturing || busy.value || !enabled.value) {
      return
    }
    if (onLiveMatches(matches)) {
      capturing = false
      armed = false
      clearTicks = 0
      liveMatchMisses = 0
      lastCaptureAt = Date.now()
      phase.value = 'cooldown'
    } else {
      liveMatchMisses += 1
    }
  }

  /** Start the detection interval (idempotent). */
  function startPump(): void {
    if (timer === null) {
      timer = setInterval(pumpFrame, FRAME_MS)
    }
  }

  /** Spawn the worker and kick off OpenCV loading inside it. */
  function startWorker(): void {
    if (worker) {
      if (ready.value) {
        phase.value = 'watching'
        startPump()
      }
      return
    }
    if (typeof Worker === 'undefined') {
      loadError.value = 'Scan auto non supporté par ce navigateur'
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

  /** Reset the per-session detection state (keeps the worker + OpenCV warm). */
  function resetTransientState(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    if (burstTimer !== null) {
      clearTimeout(burstTimer)
      burstTimer = null
    }
    if (burstWatchdog !== null) {
      clearTimeout(burstWatchdog)
      burstWatchdog = null
    }
    detectInFlight = false
    capturing = false
    armed = true
    clearTicks = 0
    lastCorners = null
    displayedCorners = null
    pendingCorners = null
    missTicks = 0
    burstCorners = null
    burstShots = []
    burstMisses = 0
    blurRetries = 0
    liveMatchMisses = 0
    quad.value = null
    phase.value = ready.value ? 'idle' : phase.value
  }

  /**
   * Pause detection without killing the worker: re-enabling used to reload the
   * whole ~9 MB OpenCV wasm on every switch toggle or camera change.
   */
  function pause(): void {
    resetTransientState()
    phase.value = 'idle'
  }

  /**
   * Hand the prebuilt visual-match index to the worker (posted immediately
   * when the worker is up, or kept until its `ready` message otherwise).
   * @param buf - Raw `index-v{N}.bin` payload (`GPXI` header + packed hashes).
   */
  function setMatchIndex(buf: ArrayBuffer): void {
    pendingIndexBuffer = buf
    if (worker && ready.value) {
      worker.postMessage({ t: 'index', buf })
    }
  }

  /** Tear everything down (page unmount only). */
  function stopAll(): void {
    resetTransientState()
    if (worker) {
      worker.terminate()
      worker = null
    }
    detectCanvas = null
    detectCtx = null
    captureCanvas = null
    captureCtx = null
    ready.value = false
    matchIndexReady.value = false
    phase.value = 'idle'
  }

  watch(
    enabled,
    (on) => {
      if (on) {
        startWorker()
      } else {
        pause()
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(stopAll)

  return { phase, quad, ready, loadError, matchIndexReady, setMatchIndex }
}
