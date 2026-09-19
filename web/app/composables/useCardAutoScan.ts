import type { ComputedRef, Ref } from 'vue'

/**
 * - `idle`      : detector stopped / OpenCV not ready
 * - `watching`  : searching — no identified card on screen
 * - `cooldown`  : a card was committed; waiting for it to leave the frame
 */
export type AutoScanPhase = 'idle' | 'watching' | 'cooldown'

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
  /** `true` while an upload is in flight; identification pauses then. */
  busy: Ref<boolean>
  /** `true` when the identifier worker (embedding index) is ready. */
  identifyActive: Ref<boolean> | ComputedRef<boolean>
  /**
   * Live identification crops: deskewed 224×224 RGBA candidates (tracked
   * quad, or search-window variants whose zone is given in video coords).
   * The page runs the embedding + decision, then calls `reportIdentifyOutcome`.
   */
  onIdentifyCrop?: (bufs: ArrayBuffer[]) => void
}

/** ~20 fps cadence — point tracking costs 3-6 ms/frame, so the overlay can glue. */
const FRAME_MS = 50
/** Long edge of the downscaled frame sent for detection (more = sharper quad). */
const PROC_EDGE = 640
/**
 * Empty detection ticks required after a capture before the next card can
 * fire. Two frames (~160 ms) was far too short: a flickering contour made
 * the scanner re-arm while the same card was still in frame → spam.
 */
const CLEAR_TICKS_TO_REARM = 10
/** Minimum quiet time after a commit before re-arming (ms). */
const MIN_REARM_MS = 900

/**
 * Durée maximale du cooldown : un suivi devenu obsolète (cadre resté collé au
 * décor) empêcherait sinon le réarmement — jamais 10 ticks sans quad.
 */
const COOLDOWN_MAX_MS = 2500
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
 * Touch-free card scanner. All OpenCV work (contour detection + point
 * tracking + identification crops) runs in a Web Worker so the ~9 MB wasm
 * never freezes the phone. The worker streams back the card quad (video-pixel
 * coords) which we **smooth** before exposing as `quad` — affiché seulement
 * quand l'identification a cautionné la zone. Le commit vient de la page
 * (worker d'embedding) via `reportIdentifyOutcome` ; le scanner attend ensuite
 * que la carte quitte le champ — passe une carte, bip, carte suivante.
 *
 * @param opts - Video element, enable/busy flags and the identify callback.
 * @returns Reactive `phase`, `quad`, `ready` and `loadError` for the UI.
 */
export function useCardAutoScan(opts: UseCardAutoScanOptions) {
  const { video, enabled, busy, identifyActive, onIdentifyCrop } = opts

  const phase: Ref<AutoScanPhase> = ref('idle')
  const quad: Ref<CardQuad | null> = ref(null)
  const ready: Ref<boolean> = ref(false)
  const loadError: Ref<string | null> = ref(null)

  let worker: Worker | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let detectCanvas: HTMLCanvasElement | null = null
  let detectCtx: CanvasRenderingContext2D | null = null

  let detectInFlight = false
  let detectSentAt = 0
  /** False right after a commit — set back to true once the frame is clear. */
  let armed = true
  let clearTicks = 0
  let displayedCorners: Pt[] | null = null
  let pendingCorners: Pt[] | null = null
  let missTicks = 0
  let lastCommitAt = 0

  /**
   * Draw the current video frame into the right scratch canvas and return its
   * transferable RGBA buffer (no `createImageBitmap` — iOS-safe).
   *
   * @param longEdge - Target long-edge size.
   * @returns The frame buffer + its pixel dimensions, or `null`.
   */
  function grabFrame(longEdge: number): { buf: ArrayBuffer; w: number; h: number } | null {
    const el = video.value
    if (!el || el.readyState < 2 || !el.videoWidth || !el.videoHeight) {
      return null
    }
    const vw = el.videoWidth
    const vh = el.videoHeight
    const scale = Math.min(1, longEdge / Math.max(vw, vh))
    const w = Math.max(1, Math.round(vw * scale))
    const h = Math.max(1, Math.round(vh * scale))
    let canvas = detectCanvas
    let ctx = detectCtx
    if (!canvas) {
      canvas = document.createElement('canvas')
      detectCanvas = canvas
    }
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      ctx = canvas.getContext('2d', { willReadFrequently: true })
      detectCtx = ctx
    }
    if (!ctx) {
      return null
    }
    ctx.drawImage(el, 0, 0, w, h)
    return { buf: ctx.getImageData(0, 0, w, h).data.buffer as ArrayBuffer, w, h }
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

    // Réarmement garanti : quad présent ou non, le cooldown a une durée max.
    if (!armed && Date.now() - lastCommitAt >= COOLDOWN_MAX_MS) {
      armed = true
      clearTicks = 0
      liveMatchMisses = 0
      phase.value = 'watching'
    }

    // No card this tick — re-arm only after sustained absence + minimum quiet time.
    if (!corners) {
      pendingCorners = null
      missTicks += 1
      if (!armed && Date.now() - lastCommitAt >= MIN_REARM_MS) {
        clearTicks += 1
        if (clearTicks >= CLEAR_TICKS_TO_REARM) {
          armed = true
          phase.value = 'watching'
        }
      }
      if (missTicks >= MISS_LINGER_TICKS) {
        displayedCorners = null
        quad.value = null
        if (phase.value !== 'idle' && armed) {
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

    // Smooth toward the confirmed quad — le détecteur neuronal donne les
    // coins de la CARTE (pas d'un rectangle du décor), le cadre s'affiche
    // dès qu'elle est vue et la suit à la cadence des frames.
    displayedCorners = smoothCorners(displayedCorners, confirmed, longEdge)
    quad.value = [displayedCorners[0]!, displayedCorners[1]!, displayedCorners[2]!, displayedCorners[3]!]

    // Not re-armed yet: the previous card is still in frame. The UI shows
    // "Retirez la carte" — and that label is now actually true.
    if (!armed) {
      phase.value = 'cooldown'
    }
  }

  /**
   * Grab one downscaled frame and hand it to the worker for detection.
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
    // Identification continue même en cooldown : elle sert alors au RECALAGE
    // du cadre sur la carte commitée (la page filtre selon la phase).
    const identify = !busy.value && identifyActive.value
    worker.postMessage(
      { t: 'detect', buf: f.buf, w: f.w, h: f.h, vw: el.videoWidth, vh: el.videoHeight, im: identify },
      [f.buf],
    )
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
      | { t: 'idcrop'; bufs: ArrayBuffer[] }
    if (d.t === 'ready') {
      ready.value = true
      loadError.value = null
      if (enabled.value) {
        phase.value = 'watching'
        startPump()
      }
      return
    }
    if (d.t === 'error') {
      // Fatal engine failure (OpenCV never loaded / crashed). Reset every
      // transient flag so a later retry starts clean instead of deadlocking.
      loadError.value = d.m
      ready.value = false
      detectInFlight = false
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
    if (d.t === 'idcrop') {
      if (onIdentifyCrop && !busy.value && enabled.value) {
        onIdentifyCrop(d.bufs)
      }
    }
  }

  /**
   * Verdict de l'identification asynchrone (worker d'embedding).
   * @param committed - `true` : carte commitée → cooldown « retirez la carte ».
   */
  function reportIdentifyOutcome(committed: boolean): void {
    if (!armed) {
      return
    }
    if (committed) {
      armed = false
      clearTicks = 0
      lastCommitAt = Date.now()
      phase.value = 'cooldown'
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
    worker.postMessage({
      t: 'init',
      ortUrl: '/ort/ort.wasm.min.js',
      wasmBase: '/ort/',
      cornerModelUrl: '/scan-model/card-corners.onnx',
    })
  }

  /** Reset the per-session detection state (keeps the worker + OpenCV warm). */
  function resetTransientState(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    detectInFlight = false
    armed = true
    clearTicks = 0
    displayedCorners = null
    pendingCorners = null
    missTicks = 0
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

  /** Tear everything down (page unmount only). */
  function stopAll(): void {
    resetTransientState()
    if (worker) {
      worker.terminate()
      worker = null
    }
    detectCanvas = null
    detectCtx = null
    ready.value = false
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

  return { phase, quad, ready, loadError, reportIdentifyOutcome }
}
