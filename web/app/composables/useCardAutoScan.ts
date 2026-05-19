import type { Ref } from 'vue'
import { loadOpenCv, type Cv } from '~/composables/useOpenCv'

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

/** Processing resolution (long edge) — detection runs on a downscale for speed. */
const PROC_EDGE = 480
/** Detector cadence. ~11 fps is plenty and keeps phones cool. */
const TICK_MS = 90
/** A card quad must cover at least this fraction of the frame. */
const MIN_AREA_RATIO = 0.14
/** Corner jitter (proc px) under which the quad is "held steady". */
const STEADY_CORNER_PX = 9
/** Consecutive steady ticks before firing (~0.5 s). */
const STEADY_TICKS = 5
/** Frames with no card before we re-arm after a capture (card removed). */
const LOST_TICKS_REARM = 3
/** Floor between two captures (anti double-shot). */
const MIN_COOLDOWN_MS = 1500
/** Output crop size sent to OCR (≈ 63:88 card ratio, sharp enough for Groq). */
const WARP_W = 630
const WARP_H = 880

/**
 * Touch-free card scanner backed by OpenCV.js: every tick it finds the largest
 * convex 4-point contour (the card), exposes it as `quad` so the UI can draw a
 * tracking outline, and when that quad is held steady it perspective-crops the
 * card and fires `onCapture` **once**. The next shot only arms after the card
 * leaves the frame — exactly the "cash register" flow, no spam on an empty view
 * (no quad ⇒ nothing happens at all).
 *
 * @param opts - Video element, enable/busy flags and the capture callback.
 * @returns Reactive `phase`, `quad` and `ready` (OpenCV loaded) for the UI.
 */
export function useCardAutoScan(opts: UseCardAutoScanOptions) {
  const { video, enabled, busy, onCapture } = opts

  const phase: Ref<AutoScanPhase> = ref('idle')
  const quad: Ref<CardQuad | null> = ref(null)
  const ready: Ref<boolean> = ref(false)
  const loadError: Ref<string | null> = ref(null)

  let cv: Cv | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let procCanvas: HTMLCanvasElement | null = null
  let procCtx: CanvasRenderingContext2D | null = null

  let lastCorners: Pt[] | null = null
  let steadyTicks = 0
  let lostTicks = 0
  let lastCaptureAt = 0
  let capturing = false

  /**
   * Order 4 points as [top-left, top-right, bottom-right, bottom-left].
   * @param pts - The four polygon vertices in any order.
   * @returns The same points, consistently ordered.
   */
  function orderCorners(pts: Pt[]): Pt[] {
    const bySum = [...pts].sort((a, b) => a.x + a.y - (b.x + b.y))
    const byDiff = [...pts].sort((a, b) => a.y - a.x - (b.y - b.x))
    const tl = bySum[0]!
    const br = bySum[3]!
    const tr = byDiff[0]!
    const bl = byDiff[3]!
    return [tl, tr, br, bl]
  }

  /**
   * Mean corner displacement between two ordered quads (proc px).
   * @param a - First ordered quad.
   * @param b - Second ordered quad.
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
   * Find the largest plausible card quad in the current frame.
   *
   * @returns Ordered corners in *proc* coords and the proc canvas size, or `null`.
   */
  function detectQuad(): { corners: Pt[]; pw: number; ph: number } | null {
    const el = video.value
    if (!cv || !el || el.readyState < 2 || !el.videoWidth || !el.videoHeight) {
      return null
    }
    const vw = el.videoWidth
    const vh = el.videoHeight
    const scale = PROC_EDGE / Math.max(vw, vh)
    const pw = Math.max(1, Math.round(vw * scale))
    const ph = Math.max(1, Math.round(vh * scale))
    if (!procCanvas) {
      procCanvas = document.createElement('canvas')
    }
    if (procCanvas.width !== pw || procCanvas.height !== ph) {
      procCanvas.width = pw
      procCanvas.height = ph
      procCtx = procCanvas.getContext('2d', { willReadFrequently: true })
    }
    if (!procCtx) {
      return null
    }
    procCtx.drawImage(el, 0, 0, pw, ph)

    const src = cv.matFromImageData(procCtx.getImageData(0, 0, pw, ph))
    const gray = new cv.Mat()
    const edges = new cv.Mat()
    const contours = new cv.MatVector()
    const hierarchy = new cv.Mat()
    let best: { corners: Pt[]; area: number } | null = null
    try {
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY)
      cv.GaussianBlur(gray, gray, new cv.Size(5, 5), 0, 0, cv.BORDER_DEFAULT)
      cv.Canny(gray, edges, 60, 180)
      const k = cv.Mat.ones(3, 3, cv.CV_8U)
      cv.dilate(edges, edges, k)
      k.delete()
      cv.findContours(edges, contours, hierarchy, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)

      const frameArea = pw * ph
      for (let i = 0; i < contours.size(); i += 1) {
        const cnt = contours.get(i)
        const area = cv.contourArea(cnt)
        if (area < frameArea * MIN_AREA_RATIO) {
          cnt.delete()
          continue
        }
        const peri = cv.arcLength(cnt, true)
        const approx = new cv.Mat()
        cv.approxPolyDP(cnt, approx, 0.02 * peri, true)
        if (approx.rows === 4 && cv.isContourConvex(approx)) {
          const corners: Pt[] = []
          for (let r = 0; r < 4; r += 1) {
            corners.push({ x: approx.intPtr(r, 0)[0], y: approx.intPtr(r, 0)[1] })
          }
          if (!best || area > best.area) {
            best = { corners: orderCorners(corners), area }
          }
        }
        approx.delete()
        cnt.delete()
      }
    } catch {
      best = null
    } finally {
      src.delete()
      gray.delete()
      edges.delete()
      contours.delete()
      hierarchy.delete()
    }
    return best ? { corners: best.corners, pw, ph } : null
  }

  /** Perspective-crop the steady card from the full-res frame → JPEG File. */
  async function warpAndEmit(cornersProc: Pt[], pw: number, ph: number): Promise<void> {
    const el = video.value
    if (!cv || !el) {
      return
    }
    const vw = el.videoWidth
    const vh = el.videoHeight
    const fx = vw / pw
    const fy = vh / ph
    const full = document.createElement('canvas')
    full.width = vw
    full.height = vh
    const fctx = full.getContext('2d')
    if (!fctx) {
      return
    }
    fctx.drawImage(el, 0, 0, vw, vh)

    const src = cv.matFromImageData(fctx.getImageData(0, 0, vw, vh))
    const dst = new cv.Mat()
    const srcTri = cv.matFromArray(
      4,
      1,
      cv.CV_32FC2,
      cornersProc.flatMap((p) => [p.x * fx, p.y * fy]),
    )
    const dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [0, 0, WARP_W, 0, WARP_W, WARP_H, 0, WARP_H])
    const out = document.createElement('canvas')
    out.width = WARP_W
    out.height = WARP_H
    try {
      const M = cv.getPerspectiveTransform(srcTri, dstTri)
      cv.warpPerspective(src, dst, M, new cv.Size(WARP_W, WARP_H), cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar())
      cv.imshow(out, dst)
      M.delete()
    } finally {
      src.delete()
      dst.delete()
      srcTri.delete()
      dstTri.delete()
    }
    const blob = await new Promise<Blob | null>((res) => out.toBlob((b) => res(b), 'image/jpeg', 0.92))
    if (!blob) {
      return
    }
    await onCapture(new File([blob], `card-${Date.now()}.jpg`, { type: 'image/jpeg' }))
  }

  /**
   * Scale proc-space corners up to video-intrinsic pixels for the overlay.
   * @param corners - Ordered corners in proc-canvas coords.
   * @param pw - Proc canvas width.
   * @param ph - Proc canvas height.
   * @returns The quad in video-intrinsic pixel coordinates.
   */
  function mapToVideo(corners: Pt[], pw: number, ph: number): CardQuad {
    const el = video.value!
    const fx = el.videoWidth / pw
    const fy = el.videoHeight / ph
    const m = corners.map((p) => ({ x: p.x * fx, y: p.y * fy }))
    return [m[0]!, m[1]!, m[2]!, m[3]!]
  }

  /**
   *
   */
  async function tick(): Promise<void> {
    if (!enabled.value || !cv || capturing) {
      return
    }
    const found = detectQuad()

    if (!found) {
      quad.value = null
      lastCorners = null
      steadyTicks = 0
      if (phase.value === 'cooldown') {
        lostTicks += 1
        if (lostTicks >= LOST_TICKS_REARM) {
          phase.value = 'watching'
        }
      } else if (phase.value !== 'idle') {
        phase.value = 'watching'
      }
      return
    }

    quad.value = mapToVideo(found.corners, found.pw, found.ph)

    // A card is being shown again right after a shot: hold until it leaves.
    if (phase.value === 'cooldown') {
      lostTicks = 0
      return
    }

    if (lastCorners && cornerDrift(found.corners, lastCorners) < STEADY_CORNER_PX) {
      steadyTicks += 1
    } else {
      steadyTicks = 0
    }
    lastCorners = found.corners

    if (steadyTicks < STEADY_TICKS || busy.value || Date.now() - lastCaptureAt < MIN_COOLDOWN_MS) {
      phase.value = 'settling'
      return
    }

    capturing = true
    lastCaptureAt = Date.now()
    steadyTicks = 0
    lostTicks = 0
    phase.value = 'captured'
    try {
      await warpAndEmit(found.corners, found.pw, found.ph)
    } finally {
      capturing = false
      phase.value = 'cooldown'
    }
  }

  /**
   *
   */
  function startLoop(): void {
    if (timer !== null) {
      return
    }
    phase.value = 'watching'
    timer = setInterval(() => {
      void tick()
    }, TICK_MS)
  }

  /**
   *
   */
  function stopLoop(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    quad.value = null
    lastCorners = null
    steadyTicks = 0
    lostTicks = 0
    phase.value = 'idle'
  }

  watch(
    enabled,
    async (on) => {
      if (!on) {
        stopLoop()
        return
      }
      if (!cv) {
        try {
          cv = await loadOpenCv()
          ready.value = true
        } catch (e) {
          loadError.value = e instanceof Error ? e.message : 'OpenCV indisponible'
          return
        }
      }
      if (enabled.value) {
        startLoop()
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(stopLoop)

  return { phase, quad, ready, loadError }
}
