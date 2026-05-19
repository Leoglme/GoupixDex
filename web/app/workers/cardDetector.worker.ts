/* eslint-disable */
// @ts-nocheck
/**
 * Card-detection Web Worker. OpenCV.js (~9 MB + wasm) is loaded and run here so
 * the heavy contour/perspective work NEVER blocks the UI thread.
 *
 * Pipeline:
 *   gray → CLAHE (adaptive contrast, fixes flash + low light)
 *        → median blur (preserves card edges, kills sensor noise)
 *        → auto-Canny (thresholds derived from image median)
 *        → morphological close (bridges glare gaps)
 *        → external contours
 *        → score top-N candidates on (aspect-ratio match, fill, convexity,
 *          convex-4 bonus, border safety) and pick the best
 *        → temporal voting + force-card-shape live main-thread
 *
 * Capture also measures sharpness (variance-of-Laplacian) so the main thread
 * can run a small "burst → pick sharpest" to combat hand-shake / focus hunt.
 *
 * Protocol (main ⇄ worker):
 *   → { t:'init', url }                              ← { t:'ready' } | { t:'error', m }
 *   → { t:'detect', buf, w, h, vw, vh }              ← { t:'quad', corners } | { t:'nq' }
 *   → { t:'warp', buf, w, h, corners }               ← { t:'warped', buf, w, h, sharpness } | { t:'error', m }
 *
 * `corners` are always VIDEO-intrinsic pixel coords.
 */

const MIN_AREA_RATIO = 0.06 // card must cover ≥6% of the frame
const MAX_FILL = 0.6 // reject quads that fill > 60% (whole-frame artifacts)
const BORDER_MARGIN = 0.015 // a real card never touches all four edges
const AR_MIN = 1.15 // card ≈ 88/63 ≈ 1.40; reject squarish blobs (hand/wall)
const AR_MAX = 1.95 // and overly elongated shapes
const CARD_AR = 1.397 // 88/63 — Pokémon card ratio
const MIN_SCORE = 0.5 // candidates below this are rejected (was 0.4 — too loose)
const TOP_N_CANDIDATES = 8
const WARP_W = 630
const WARP_H = 880

let cv: any = null

function orderCorners(pts: { x: number; y: number }[]): { x: number; y: number }[] {
  const bySum = [...pts].sort((a, b) => a.x + a.y - (b.x + b.y))
  const byDiff = [...pts].sort((a, b) => a.y - a.x - (b.y - b.x))
  return [bySum[0], byDiff[0], bySum[3], byDiff[3]]
}

function polyArea(p: { x: number; y: number }[]): number {
  let s = 0
  for (let i = 0; i < p.length; i += 1) {
    const j = (i + 1) % p.length
    s += p[i].x * p[j].y - p[j].x * p[i].y
  }
  return Math.abs(s) / 2
}

/** 4 corners of an OpenCV RotatedRect ({center,size,angle°}). */
function rrCorners(rr: any): { x: number; y: number }[] {
  const a = (rr.angle * Math.PI) / 180
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  const dx = rr.size.width / 2
  const dy = rr.size.height / 2
  return [
    [-dx, -dy],
    [dx, -dy],
    [dx, dy],
    [-dx, dy],
  ].map(([x, y]) => ({ x: rr.center.x + x * cos - y * sin, y: rr.center.y + x * sin + y * cos }))
}

/** True when the quad spans the WHOLE frame — that's not a card, that's noise. */
function spansFullFrame(pts: { x: number; y: number }[], w: number, h: number): boolean {
  const m = BORDER_MARGIN
  let touchL = false
  let touchR = false
  let touchT = false
  let touchB = false
  for (const p of pts) {
    if (p.x < w * m) touchL = true
    if (p.x > w * (1 - m)) touchR = true
    if (p.y < h * m) touchT = true
    if (p.y > h * (1 - m)) touchB = true
  }
  return touchL && touchR && touchT && touchB
}

/**
 * Score one contour as a card candidate. Higher = better. Returns null when
 * the contour fails hard filters (size, aspect, border safety).
 */
function scoreCandidate(cnt: any, w: number, h: number) {
  const frameArea = w * h
  const hull = new cv.Mat()
  cv.convexHull(cnt, hull)
  const hullArea = Math.max(1, cv.contourArea(hull))
  const cntArea = cv.contourArea(cnt)
  const convexity = Math.min(1, cntArea / hullArea) // ~1 for clean cards

  let pts: { x: number; y: number }[] | null = null
  let convex4Bonus = 1.0
  const peri = cv.arcLength(cnt, true)
  for (const ratio of [0.015, 0.02, 0.025, 0.03, 0.04, 0.05]) {
    const approx = new cv.Mat()
    cv.approxPolyDP(cnt, approx, ratio * peri, true)
    if (approx.rows === 4 && cv.isContourConvex(approx)) {
      pts = []
      for (let r = 0; r < 4; r += 1) {
        pts.push({ x: approx.intPtr(r, 0)[0], y: approx.intPtr(r, 0)[1] })
      }
      convex4Bonus = 1.7
      approx.delete()
      break
    }
    approx.delete()
  }

  if (!pts) {
    pts = rrCorners(cv.minAreaRect(hull))
  }
  hull.delete()

  const ordered = orderCorners(pts)
  if (spansFullFrame(ordered, w, h)) {
    return null
  }

  const polygon = polyArea(ordered)
  const fill = polygon / frameArea
  if (fill > MAX_FILL || fill < MIN_AREA_RATIO) {
    return null
  }

  const wEdge = Math.hypot(ordered[1].x - ordered[0].x, ordered[1].y - ordered[0].y)
  const hEdge = Math.hypot(ordered[3].x - ordered[0].x, ordered[3].y - ordered[0].y)
  const longEdge = Math.max(wEdge, hEdge)
  const shortEdge = Math.max(1, Math.min(wEdge, hEdge))
  const ar = longEdge / shortEdge
  if (ar < AR_MIN || ar > AR_MAX) {
    return null
  }

  // Strongly reward AR near the card's. Narrow falloff (was 0.55).
  const arDelta = Math.abs(ar - CARD_AR)
  const arScore = Math.max(0, 1 - arDelta / 0.3)

  // Prefer 20–55% fill. Anything over 60% already rejected above.
  const fillScore = fill < 0.12 ? Math.max(0, fill / 0.12) : fill > 0.5 ? Math.max(0, 1 - (fill - 0.5) / 0.1) : 1

  // Convexity boost
  const convexityScore = Math.min(1, convexity * 1.05)

  // Aspect ratio is now the dominant signal; the others are tie-breakers.
  const score = arScore * 0.62 + fillScore * 0.22 + convexityScore * 0.16
  return { pts: ordered, score: score * convex4Bonus }
}

function waitForCv(resolve: () => void, reject: (m: string) => void): void {
  const g = self as any
  let tries = 0
  const tick = (): void => {
    tries += 1
    if (g.cv && typeof g.cv.Mat === 'function') {
      cv = g.cv
      resolve()
      return
    }
    if (g.cv && typeof g.cv.then === 'function' && tries === 1) {
      try {
        g.cv.then((m: any) => {
          if (m && typeof m.Mat === 'function') {
            g.cv = m
          }
        })
      } catch {}
    }
    if (g.cv) {
      g.cv.onRuntimeInitialized = (): void => {
        cv = g.cv
        resolve()
      }
    }
    if (tries >= 600) {
      reject('OpenCV: délai d’initialisation dépassé')
      return
    }
    setTimeout(tick, 100)
  }
  tick()
}

/** Detect the best card quad with multi-candidate scoring. */
function detect(buf: ArrayBuffer, w: number, h: number, vw: number, vh: number) {
  const img = new ImageData(new Uint8ClampedArray(buf), w, h)
  const src = cv.matFromImageData(img)
  const gray = new cv.Mat()
  const enhanced = new cv.Mat()
  const blurred = new cv.Mat()
  const edges = new cv.Mat()
  const contours = new cv.MatVector()
  const hierarchy = new cv.Mat()
  let chosen: { x: number; y: number }[] | null = null
  try {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY)

    let claheOk = false
    try {
      const clahe = new cv.CLAHE(2.5, new cv.Size(8, 8))
      clahe.apply(gray, enhanced)
      clahe.delete()
      claheOk = true
    } catch {
      claheOk = false
    }
    const base = claheOk ? enhanced : gray

    cv.medianBlur(base, blurred, 5)

    const meanScalar = cv.mean(blurred)[0]
    const lower = Math.max(10, Math.round(0.66 * meanScalar))
    const upper = Math.max(lower + 25, Math.round(1.33 * meanScalar))
    cv.Canny(blurred, edges, lower, upper)

    const k = cv.Mat.ones(5, 5, cv.CV_8U)
    cv.morphologyEx(edges, edges, cv.MORPH_CLOSE, k)
    k.delete()

    cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    const frameArea = w * h
    const cands: { cnt: any; area: number }[] = []
    for (let i = 0; i < contours.size(); i += 1) {
      const cnt = contours.get(i)
      const area = cv.contourArea(cnt)
      if (area < frameArea * MIN_AREA_RATIO) {
        cnt.delete()
        continue
      }
      cands.push({ cnt, area })
    }
    cands.sort((a, b) => b.area - a.area)
    for (let i = TOP_N_CANDIDATES; i < cands.length; i += 1) {
      cands[i].cnt.delete()
    }
    cands.length = Math.min(TOP_N_CANDIDATES, cands.length)

    let bestScore = -1
    let bestPts: { x: number; y: number }[] | null = null
    for (const c of cands) {
      const result = scoreCandidate(c.cnt, w, h)
      if (result && result.score > bestScore) {
        bestScore = result.score
        bestPts = result.pts
      }
    }
    for (const c of cands) {
      c.cnt.delete()
    }

    if (bestPts && bestScore >= MIN_SCORE) {
      const fx = vw / w
      const fy = vh / h
      chosen = bestPts.map((p) => ({ x: p.x * fx, y: p.y * fy }))
    }
  } catch {
    chosen = null
  } finally {
    src.delete()
    gray.delete()
    enhanced.delete()
    blurred.delete()
    edges.delete()
    contours.delete()
    hierarchy.delete()
  }
  return chosen
}

/** Perspective-deskew the card and measure focus sharpness. */
function warp(buf: ArrayBuffer, w: number, h: number, corners: { x: number; y: number }[]) {
  const img = new ImageData(new Uint8ClampedArray(buf), w, h)
  const src = cv.matFromImageData(img)
  const dst = new cv.Mat()
  const srcTri = cv.matFromArray(
    4,
    1,
    cv.CV_32FC2,
    corners.flatMap((p) => [p.x, p.y]),
  )
  const dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [0, 0, WARP_W, 0, WARP_W, WARP_H, 0, WARP_H])
  let sharpness = 0
  try {
    const M = cv.getPerspectiveTransform(srcTri, dstTri)
    cv.warpPerspective(src, dst, M, new cv.Size(WARP_W, WARP_H), cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar())
    M.delete()

    const gray = new cv.Mat()
    const lap = new cv.Mat()
    const absLap = new cv.Mat()
    cv.cvtColor(dst, gray, cv.COLOR_RGBA2GRAY)
    cv.Laplacian(gray, lap, cv.CV_64F)
    cv.convertScaleAbs(lap, absLap)
    const m = cv.mean(absLap)
    sharpness = Array.isArray(m) ? m[0] : m
    gray.delete()
    lap.delete()
    absLap.delete()

    return { out: new Uint8ClampedArray(dst.data).buffer, sharpness }
  } finally {
    src.delete()
    dst.delete()
    srcTri.delete()
    dstTri.delete()
  }
}

self.onmessage = (e: MessageEvent): void => {
  const d = e.data
  if (d.t === 'init') {
    try {
      ;(self as any).importScripts(d.url)
    } catch {
      ;(self as any).postMessage({ t: 'error', m: 'OpenCV: chargement échoué' })
      return
    }
    waitForCv(
      () => (self as any).postMessage({ t: 'ready' }),
      (m: string) => (self as any).postMessage({ t: 'error', m }),
    )
    return
  }
  if (!cv) {
    return
  }
  if (d.t === 'detect') {
    let corners = null
    try {
      corners = detect(d.buf, d.w, d.h, d.vw, d.vh)
    } catch {
      corners = null
    }
    ;(self as any).postMessage(corners ? { t: 'quad', corners } : { t: 'nq' })
    return
  }
  if (d.t === 'warp') {
    try {
      const { out, sharpness } = warp(d.buf, d.w, d.h, d.corners)
      ;(self as any).postMessage({ t: 'warped', buf: out, w: WARP_W, h: WARP_H, sharpness }, [out])
    } catch {
      ;(self as any).postMessage({ t: 'error', m: 'Découpe carte impossible' })
    }
    return
  }
}
