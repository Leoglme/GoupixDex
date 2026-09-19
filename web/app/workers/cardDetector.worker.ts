/* eslint-disable */
// @ts-nocheck
/**
 * Card-detection Web Worker. OpenCV.js (~9 MB + wasm) is loaded and run here so
 * the heavy contour/perspective work NEVER blocks the UI thread.
 *
 * Pipeline:
 *   gray → CLAHE (adaptive contrast, fixes flash + low light)
 *        → median blur (preserves card edges, kills sensor noise)
 *        → auto-Canny (thresholds derived from the true image median)
 *        → morphological close (bridges glare gaps)
 *        → external contours
 *        → score top-N candidates on (aspect-ratio match, fill, convexity,
 *          convex-4 bonus, border safety) and pick the best
 *        → temporal voting + force-card-shape live main-thread
 *
 * Protocol (main ⇄ worker):
 *   → { t:'init', url }                        ← { t:'ready' } | { t:'error', m }   (fatal: engine unavailable)
 *   → { t:'detect', buf, w, h, vw, vh, im }    ← { t:'quad', corners } | { t:'nq' } (+ { t:'idcrop', bufs, wins, sharps })
 *   → { t:'lock', rect } / { t:'focus', rect } / { t:'droptrack' }
 *
 * `corners` are always VIDEO-intrinsic pixel coords.
 */

const MIN_AREA_RATIO = 0.06 // card must cover ≥6% of the frame
const MAX_FILL = 0.45 // above this the "quad" is the desk/screen, not a hand-held card
const BORDER_MARGIN = 0.03 // corner closer than 3% to an edge counts as touching it
const AR_MIN = 1.05 // card ≈ 88/63 ≈ 1.40; perspective can compress the ratio a lot
const AR_MAX = 1.95 // reject overly elongated shapes
const CARD_AR = 1.397 // 88/63 — Pokémon card ratio
const MIN_SCORE = 0.45
const TOP_N_CANDIDATES = 8
const WARP_W = 630
const WARP_H = 880

let cv: any = null

/**
 * Order 4 points as TL, TR, BR, BL. TL/BR come from the x+y extremes; the two
 * remaining points are split on x−y. Identity-based so a rotated (diamond)
 * quad can never yield the same point twice — the old sum/diff double-sort
 * did, which made getPerspectiveTransform throw and killed the scanner.
 */
function orderCorners(pts: { x: number; y: number }[]): { x: number; y: number }[] {
  const bySum = [...pts].sort((a, b) => a.x + a.y - (b.x + b.y))
  const tl = bySum[0]
  const br = bySum[3]
  const rest = pts.filter((p) => p !== tl && p !== br)
  if (rest.length !== 2) {
    return pts.slice(0, 4)
  }
  const [p1, p2] = rest
  const tr = p1.x - p1.y >= p2.x - p2.y ? p1 : p2
  const bl = tr === p1 ? p2 : p1
  return [tl, tr, br, bl]
}

function polyArea(p: { x: number; y: number }[]): number {
  let s = 0
  for (let i = 0; i < p.length; i += 1) {
    const j = (i + 1) % p.length
    s += p[i].x * p[j].y - p[j].x * p[i].y
  }
  return Math.abs(s) / 2
}

/** True when any two corners are (near) coincident — warp would be degenerate. */
function hasDegenerateCorners(pts: { x: number; y: number }[]): boolean {
  for (let i = 0; i < pts.length; i += 1) {
    for (let j = i + 1; j < pts.length; j += 1) {
      if (Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y) < 4) {
        return true
      }
    }
  }
  return false
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

/**
 * True when the quad spans the frame — that's the table / a lap / the scene
 * boundary, never a card. Three touched borders already means the shape runs
 * off-screen (a real card at cash-register distance keeps at least two edges
 * fully visible), so ≥3 is rejected, not just all four.
 */
function spansFullFrame(pts: { x: number; y: number }[], w: number, h: number): boolean {
  const m = BORDER_MARGIN
  let touched = 0
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
  touched = Number(touchL) + Number(touchR) + Number(touchT) + Number(touchB)
  return touched >= 3
}

/** True median of an 8-bit single-channel Mat (sampled — plenty at 640 px). */
function matMedian(mat: any): number {
  const data = mat.data
  const step = Math.max(1, Math.floor(data.length / 40_000))
  const sample: number[] = []
  for (let i = 0; i < data.length; i += step) {
    sample.push(data[i])
  }
  sample.sort((a, b) => a - b)
  return sample[Math.floor(sample.length / 2)] ?? 128
}

/**
 * Score one contour as a card candidate. Higher = better. Returns null when
 * the contour fails hard filters (size, aspect, border safety).
 */
function scoreCandidate(cnt: any, w: number, h: number) {
  const frameArea = w * h
  const hull = new cv.Mat()
  let pts: { x: number; y: number }[] | null = null
  let convex4Bonus = 1.0
  let convexity = 0
  try {
    cv.convexHull(cnt, hull)
    const hullArea = Math.max(1, cv.contourArea(hull))
    const cntArea = cv.contourArea(cnt)
    convexity = Math.min(1, cntArea / hullArea) // ~1 for clean cards

    const peri = cv.arcLength(cnt, true)
    for (const ratio of [0.015, 0.02, 0.025, 0.03, 0.04, 0.05]) {
      const approx = new cv.Mat()
      try {
        cv.approxPolyDP(cnt, approx, ratio * peri, true)
        if (approx.rows === 4 && cv.isContourConvex(approx)) {
          pts = []
          for (let r = 0; r < 4; r += 1) {
            pts.push({ x: approx.intPtr(r, 0)[0], y: approx.intPtr(r, 0)[1] })
          }
          convex4Bonus = 1.7
          break
        }
      } finally {
        approx.delete()
      }
    }

    if (!pts) {
      pts = rrCorners(cv.minAreaRect(hull))
    }
  } finally {
    hull.delete()
  }

  const ordered = orderCorners(pts)
  if (spansFullFrame(ordered, w, h) || hasDegenerateCorners(ordered)) {
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

  // Reward AR near the card's, with a falloff wide enough to survive the
  // perspective compression of a tilted card.
  const arDelta = Math.abs(ar - CARD_AR)
  const arScore = Math.max(0, 1 - arDelta / 0.45)

  // Plateau between 15% and 35% fill — a hand-held card rarely covers more;
  // bigger quads are almost always the desk or a screen behind the card.
  const fillScore = fill < 0.15 ? Math.max(0, fill / 0.15) : fill > 0.35 ? Math.max(0, 1 - (fill - 0.35) / 0.1) : 1

  // Convexity boost
  const convexityScore = Math.min(1, convexity * 1.05)

  const score = arScore * 0.5 + fillScore * 0.3 + convexityScore * 0.2
  return { pts: ordered, score: score * convex4Bonus }
}

function waitForCv(resolve: () => void, reject: (m: string) => void): void {
  const g = self as any
  let tries = 0
  // The polling tick, the `.then` unwrap and `onRuntimeInitialized` can all
  // fire — settle exactly once so the main thread never sees two `ready`s.
  let settled = false
  const settle = (): void => {
    if (settled) {
      return
    }
    settled = true
    cv = g.cv
    resolve()
  }
  const tick = (): void => {
    if (settled) {
      return
    }
    tries += 1
    if (g.cv && typeof g.cv.Mat === 'function') {
      settle()
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
        settle()
      }
    }
    if (tries >= 600) {
      settled = true
      reject('OpenCV: délai d’initialisation dépassé')
      return
    }
    setTimeout(tick, 100)
  }
  tick()
}

/**
 * Detect the best card quad with multi-candidate scoring. Returns both the
 * video-intrinsic corners (for the overlay) and the detection-frame corners
 * (for the on-frame identification warp), or null.
 */
function detect(buf: ArrayBuffer, w: number, h: number, vw: number, vh: number) {
  const img = new ImageData(new Uint8ClampedArray(buf), w, h)
  const src = cv.matFromImageData(img)
  const gray = new cv.Mat()
  const enhanced = new cv.Mat()
  const blurred = new cv.Mat()
  const edges = new cv.Mat()
  const contours = new cv.MatVector()
  const hierarchy = new cv.Mat()
  const cands: { cnt: any; area: number }[] = []
  let chosen: { video: { x: number; y: number }[]; frame: { x: number; y: number }[] } | null = null
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

    // Canny thresholds from the true median (mean drifts badly on dark or
    // very bright backgrounds and used to make detection light-dependent).
    const median = matMedian(blurred)
    const lower = Math.max(20, Math.round(0.66 * median))
    const upper = Math.max(lower + 30, Math.round(1.33 * median))
    cv.Canny(blurred, edges, lower, upper)

    const k = cv.Mat.ones(5, 5, cv.CV_8U)
    cv.morphologyEx(edges, edges, cv.MORPH_CLOSE, k)
    k.delete()

    cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    const frameArea = w * h
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

    if (bestPts && bestScore >= MIN_SCORE) {
      const fx = vw / w
      const fy = vh / h
      chosen = { video: bestPts.map((p) => ({ x: p.x * fx, y: p.y * fy })), frame: bestPts }
    }
  } catch {
    chosen = null
  } finally {
    // Candidate contours are deleted here (not mid-loop) so a throwing
    // scoreCandidate can never leak the remaining Mats — at 10 fps a leak
    // grows the wasm heap until the tab dies.
    for (const c of cands) {
      try {
        c.cnt.delete()
      } catch {}
    }
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

/** Perspective-deskew the card; sharpness (variance of Laplacian) is optional. */
function warp(
  buf: ArrayBuffer,
  w: number,
  h: number,
  corners: { x: number; y: number }[],
  outW: number = WARP_W,
  outH: number = WARP_H,
  measureSharpness: boolean = true,
) {
  const img = new ImageData(new Uint8ClampedArray(buf), w, h)
  const src = cv.matFromImageData(img)
  const dst = new cv.Mat()
  const srcTri = cv.matFromArray(
    4,
    1,
    cv.CV_32FC2,
    corners.flatMap((p) => [p.x, p.y]),
  )
  const dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [0, 0, outW, 0, outW, outH, 0, outH])
  let sharpness = 0
  try {
    const M = cv.getPerspectiveTransform(srcTri, dstTri)
    cv.warpPerspective(src, dst, M, new cv.Size(outW, outH), cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar())
    M.delete()

    if (measureSharpness) {
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
    }

    return { out: new Uint8ClampedArray(dst.data).buffer, sharpness }
  } finally {
    src.delete()
    dst.delete()
    srcTri.delete()
    dstTri.delete()
  }
}

// ---------------------------------------------------------------------------
// Identification crops. The worker does NOT identify cards itself any more:
// it produces deskewed 224×224 RGBA crops (tracked quad, else sweeping search
// windows) and posts them to the main thread, which runs the MobileNet
// embedding + cosine matching (see useScanEmbedIndex). Contours die on
// fingers over the card edges, so the windows sweep scale and position.
// ---------------------------------------------------------------------------

const ID_CROP_EDGE = 224
/** Floor between two crop shipments (~3/s) — inference is main-thread work. */
const ID_CROP_MIN_INTERVAL_MS = 300
/** A quad is only worth identifying when it plausibly frames a close card. */
const ID_QUAD_MIN_HEIGHT_FRAC = 0.4
const ID_QUAD_AR_MIN = 1.1
const ID_QUAD_AR_MAX = 1.9

const ID_WINDOWS: { hFrac: number; dx: number; dy: number }[] = [
  { hFrac: 0.66, dx: 0, dy: 0 },
  { hFrac: 0.66, dx: -0.08, dy: 0 },
  { hFrac: 0.66, dx: 0.08, dy: 0 },
  { hFrac: 0.66, dx: 0, dy: -0.06 },
  { hFrac: 0.66, dx: 0, dy: 0.06 },
]
let idWindowCursor = 0
let lastIdCropAt = 0
/** Alternate quad/window attempts — a bogus tracked quad must never starve the sweep. */
let idAttemptParity = 0
/** Promising zone (video coords) the main thread asked to search around. */
let focusRect: { x: number; y: number; w: number; h: number } | null = null
let focusUntil = 0
/** How long a focus request keeps steering the window sweep (ms). */
const FOCUS_TTL_MS = 2000
/**
 * Batterie expédiée à chaque tentative focalisée : une ÉCHELLE de tailles et
 * deux décalages, centrés sur la zone prometteuse. Le main thread renvoie la
 * zone du crop GAGNANT comme nouveau focus, donc la recherche converge en
 * taille ET en position (la similarité est très sensible à la géométrie :
 * ~4 % d'écart de cadrage coûtent ~0.1 de cosinus).
 */
const FOCUS_BATTERY: { k: number; dx: number; dy: number }[] = [
  { k: 1.15, dx: 0, dy: 0 },
  { k: 1, dx: 0, dy: 0 },
  { k: 0.85, dx: 0, dy: 0 },
  { k: 0.72, dx: 0, dy: 0 },
  { k: 0.85, dx: -0.05, dy: 0 },
  { k: 0.85, dx: 0.05, dy: 0 },
]

/** Card-ratio rect of one search window, in frame pixels. */
function idWindowRect(win: { hFrac: number; dx: number; dy: number }, w: number, h: number) {
  const rh = Math.round(h * win.hFrac)
  const rw = Math.min(w, Math.round((rh * 63) / 88))
  const x = Math.round((w - rw) / 2 + win.dx * w)
  const y = Math.round((h - rh) / 2 + win.dy * h)
  return { x: Math.max(0, Math.min(w - rw, x)), y: Math.max(0, Math.min(h - rh, y)), w: rw, h: rh }
}

/** True when the tracked quad plausibly frames a close, portrait card. */
function quadWorthIdentifying(quad: { x: number; y: number }[], h: number): boolean {
  const wEdge =
    (Math.hypot(quad[1].x - quad[0].x, quad[1].y - quad[0].y) +
      Math.hypot(quad[2].x - quad[3].x, quad[2].y - quad[3].y)) /
    2
  const hEdge =
    (Math.hypot(quad[3].x - quad[0].x, quad[3].y - quad[0].y) +
      Math.hypot(quad[2].x - quad[1].x, quad[2].y - quad[1].y)) /
    2
  if (hEdge < h * ID_QUAD_MIN_HEIGHT_FRAC) {
    return false
  }
  const ar = hEdge / Math.max(1, wEdge)
  return ar >= ID_QUAD_AR_MIN && ar <= ID_QUAD_AR_MAX
}

/** Rect corners helper. */
function rectCorners(rect: { x: number; y: number; w: number; h: number }): { x: number; y: number }[] {
  return [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.w, y: rect.y },
    { x: rect.x + rect.w, y: rect.y + rect.h },
    { x: rect.x, y: rect.y + rect.h },
  ]
}

/**
 * Produce identification crops (RGBA 224×224, same square distortion as the
 * index builder) and post them to the main thread. Attempts ALTERNATE between
 * the tracked quad (when it plausibly frames a card) and the sweeping search
 * windows; window attempts ship a ladder of scales (focused ones, the
 * FOCUS_BATTERY) so the right framing lands without the exact window turn.
 * The decision comes back asynchronously as a `lock` message + cooldown —
 * never through this reply channel.
 */
function shipIdentificationCrop(
  buf: ArrayBuffer,
  w: number,
  h: number,
  vw: number,
  vh: number,
  frameQuad: { x: number; y: number }[] | null,
): void {
  idAttemptParity += 1
  // Pendant un focus actif, la parité alterne batterie focalisée / balayage
  // normal (jamais le quad suivi, dont les crops sont moins bons — mesuré
  // 0.47 vs 0.59) : la convergence garde sa cadence ET le balayage peut
  // découvrir un candidat plus fort qui reprendra le focus.
  const focusActive = focusRect !== null && Date.now() < focusUntil
  const focusedAttempt = focusActive && idAttemptParity % 2 === 0
  const useQuad = !focusActive && frameQuad !== null && idAttemptParity % 2 === 0 && quadWorthIdentifying(frameQuad, h)
  if (useQuad) {
    const { out, sharpness } = warp(buf, w, h, frameQuad!, ID_CROP_EDGE, ID_CROP_EDGE, true)
    ;(self as any).postMessage({ t: 'idcrop', bufs: [out], sharps: [sharpness] }, [out])
    return
  }
  let rect: { x: number; y: number; w: number; h: number }
  if (focusedAttempt) {
    const sx = w / vw
    const sy = h / vh
    rect = { x: focusRect!.x * sx, y: focusRect!.y * sy, w: focusRect!.w * sx, h: focusRect!.h * sy }
  } else {
    rect = idWindowRect(ID_WINDOWS[idWindowCursor % ID_WINDOWS.length], w, h)
    idWindowCursor += 1
  }
  const bufs: ArrayBuffer[] = []
  const sharps: number[] = []
  const variantRects: { x: number; y: number; w: number; h: number }[] = []
  if (focusedAttempt) {
    const cx = rect.x + rect.w / 2
    const cy = rect.y + rect.h / 2
    for (const b of FOCUS_BATTERY) {
      const bw = Math.round(rect.w * b.k)
      const bh = Math.round(rect.h * b.k)
      const v = {
        x: Math.max(0, Math.min(w - bw, Math.round(cx - bw / 2 + b.dx * rect.w))),
        y: Math.max(0, Math.min(h - bh, Math.round(cy - bh / 2 + b.dy * rect.h))),
        w: bw,
        h: bh,
      }
      const { out, sharpness } = warp(buf, w, h, rectCorners(v), ID_CROP_EDGE, ID_CROP_EDGE, true)
      bufs.push(out)
      sharps.push(sharpness)
      variantRects.push(v)
    }
  } else {
    // Multi-échelles CENTRÉES par tentative : la taille apparente de la carte
    // varie du simple au double selon la distance de la main — chaque tentative
    // couvre tout ce spectre au lieu d'attendre le bon tour de la liste.
    const scaled = (k: number, dyFrac: number) => {
      const sw = Math.round(rect.w * k)
      const sh = Math.round(rect.h * k)
      return {
        x: Math.max(0, Math.min(w - sw, rect.x + Math.round((rect.w - sw) / 2))),
        y: Math.max(0, Math.min(h - sh, rect.y + Math.round((rect.h - sh) / 2 + dyFrac * rect.h))),
        w: sw,
        h: sh,
      }
    }
    const variants = [scaled(1, 0), scaled(0.87, 0), scaled(0.76, 0), scaled(0.66, 0), scaled(0.57, 0)]
    for (const v of variants) {
      const { out, sharpness } = warp(buf, w, h, rectCorners(v), ID_CROP_EDGE, ID_CROP_EDGE, true)
      bufs.push(out)
      sharps.push(sharpness)
      variantRects.push(v)
    }
  }
  // Une zone PAR variante : le main thread verrouille/focalise la zone du
  // crop GAGNANT, pas la fenêtre de base (souvent plus grande que la carte).
  const fx = vw / w
  const fy = vh / h
  const wins = variantRects.map((v) => ({ x: v.x * fx, y: v.y * fy, w: v.w * fx, h: v.h * fy }))
  ;(self as any).postMessage({ t: 'idcrop', bufs, wins, sharps }, bufs)
}

// ---------------------------------------------------------------------------
// Point tracking (optical flow). Contour detection only ACQUIRES the card;
// from then on ~60 texture points inside the quad are followed frame-to-frame
// (Lucas-Kanade) and a similarity transform moves the quad with them. This is
// what glues the overlay to a moving, shaking, even blurry card — contours
// alone flicker on wood grain and sleeve glare. Detection re-runs periodically
// to re-align (drift) or re-acquire (new card).
// ---------------------------------------------------------------------------

/** Surviving LK points below this ⇒ the track is lost. */
const TRACK_MIN_POINTS = 12
/** Re-seed fresh feature points when the pool shrinks under this. */
const TRACK_RESEED_POINTS = 25
/** Re-seed cadence (frames) even when the pool is healthy. */
const TRACK_RESEED_EVERY = 10
/** Contour re-detection cadence (frames) while tracking — re-aligns drift. */
const TRACK_REDETECT_EVERY = 8
/** Per-frame scale outside this range ⇒ bogus transform, drop the track. */
const TRACK_SCALE_STEP_MIN = 0.75
const TRACK_SCALE_STEP_MAX = 1.35

let trackGray: any = null
let trackPts: any = null
let trackQuad: { x: number; y: number }[] | null = null
let trackFrames = 0
let trackW = 0
let trackH = 0
/** Rect (video coords) the main thread asked to start tracking on (identified window). */
let pendingLockRect: { x: number; y: number; w: number; h: number } | null = null

function resetTrack(): void {
  try {
    trackGray?.delete()
  } catch {}
  try {
    trackPts?.delete()
  } catch {}
  trackGray = null
  trackPts = null
  trackQuad = null
  trackFrames = 0
}

/** Feature points inside the (slightly shrunk) quad, as a CV_32FC2 Mat — or null. */
function seedTrackPoints(gray: any, quadPts: { x: number; y: number }[]): any {
  const cx = (quadPts[0].x + quadPts[1].x + quadPts[2].x + quadPts[3].x) / 4
  const cy = (quadPts[0].y + quadPts[1].y + quadPts[2].y + quadPts[3].y) / 4
  const flat: number[] = []
  for (const p of quadPts) {
    flat.push(Math.round(cx + (p.x - cx) * 0.88), Math.round(cy + (p.y - cy) * 0.88))
  }
  const mask = cv.Mat.zeros(gray.rows, gray.cols, cv.CV_8UC1)
  const poly = cv.matFromArray(4, 1, cv.CV_32SC2, flat)
  const polys = new cv.MatVector()
  polys.push_back(poly)
  const corners = new cv.Mat()
  try {
    cv.fillPoly(mask, polys, new cv.Scalar(255))
    cv.goodFeaturesToTrack(gray, corners, 60, 0.01, 7, mask, 7)
  } catch {
    corners.delete()
    mask.delete()
    poly.delete()
    polys.delete()
    return null
  }
  mask.delete()
  poly.delete()
  polys.delete()
  if (corners.rows < TRACK_MIN_POINTS) {
    corners.delete()
    return null
  }
  return corners
}

/**
 * Closed-form 2D similarity (scale+rotation+translation) mapping `from` onto
 * `to`, with one median-based outlier rejection pass. Returns the 4 transform
 * coefficients or null when the fit is unusable.
 */
function fitSimilarity(
  from: { x: number; y: number }[],
  to: { x: number; y: number }[],
): { a: number; b: number; tx: number; ty: number; meanResidual: number; inlierRatio: number } | null {
  const solve = (idx: number[]) => {
    let pcx = 0
    let pcy = 0
    let qcx = 0
    let qcy = 0
    for (const i of idx) {
      pcx += from[i].x
      pcy += from[i].y
      qcx += to[i].x
      qcy += to[i].y
    }
    const n = idx.length
    pcx /= n
    pcy /= n
    qcx /= n
    qcy /= n
    let sa = 0
    let sb = 0
    let sd = 0
    for (const i of idx) {
      const px = from[i].x - pcx
      const py = from[i].y - pcy
      const qx = to[i].x - qcx
      const qy = to[i].y - qcy
      sa += px * qx + py * qy
      sb += px * qy - py * qx
      sd += px * px + py * py
    }
    if (sd < 1e-6) {
      return null
    }
    const a = sa / sd
    const b = sb / sd
    return { a, b, tx: qcx - (a * pcx - b * pcy), ty: qcy - (b * pcx + a * pcy) }
  }
  const all = from.map((_, i) => i)
  const first = solve(all)
  if (!first) {
    return null
  }
  const residuals = all.map((i) => {
    const x = first.a * from[i].x - first.b * from[i].y + first.tx
    const y = first.b * from[i].x + first.a * from[i].y + first.ty
    return Math.hypot(x - to[i].x, y - to[i].y)
  })
  const sorted = [...residuals].sort((p, q) => p - q)
  const cutoff = Math.max(1.5, sorted[sorted.length >> 1] * 2.5)
  const inliers = all.filter((i) => residuals[i] <= cutoff)
  const finish = (fit: { a: number; b: number; tx: number; ty: number }, idx: number[]) => {
    let acc = 0
    for (const i of idx) {
      const x = fit.a * from[i].x - fit.b * from[i].y + fit.tx
      const y = fit.b * from[i].x + fit.a * from[i].y + fit.ty
      acc += Math.hypot(x - to[i].x, y - to[i].y)
    }
    return { ...fit, meanResidual: acc / idx.length, inlierRatio: inliers.length / all.length }
  }
  if (inliers.length < 8) {
    return inliers.length >= TRACK_MIN_POINTS ? finish(first, all) : null
  }
  const refined = solve(inliers)
  return finish(refined ?? first, inliers)
}

/**
 * One optical-flow step: follow the seeded points into `gray` and move the
 * quad with the fitted similarity. Updates the track state; returns the new
 * quad (frame coords) or null when the track is lost.
 */
function stepTrack(gray: any): { x: number; y: number }[] | null {
  const next = new cv.Mat()
  const status = new cv.Mat()
  const err = new cv.Mat()
  try {
    cv.calcOpticalFlowPyrLK(trackGray, gray, trackPts, next, status, err)
    const prevData = trackPts.data32F
    const nextData = next.data32F
    const from: { x: number; y: number }[] = []
    const to: { x: number; y: number }[] = []
    for (let i = 0; i < status.rows; i += 1) {
      if (status.data[i] === 1) {
        from.push({ x: prevData[i * 2], y: prevData[i * 2 + 1] })
        to.push({ x: nextData[i * 2], y: nextData[i * 2 + 1] })
      }
    }
    if (from.length < TRACK_MIN_POINTS || !trackQuad) {
      return null
    }
    const fit = fitSimilarity(from, to)
    if (!fit) {
      return null
    }
    // A swapped/occluded card yields incoherent LK correspondences: high
    // residuals or a majority of outliers ⇒ drop the track and re-detect
    // right away instead of dragging a ghost frame around.
    if (fit.meanResidual > 2.5 || fit.inlierRatio < 0.55) {
      return null
    }
    const scale = Math.hypot(fit.a, fit.b)
    if (scale < TRACK_SCALE_STEP_MIN || scale > TRACK_SCALE_STEP_MAX) {
      return null
    }
    const moved = trackQuad.map((p) => ({
      x: fit.a * p.x - fit.b * p.y + fit.tx,
      y: fit.b * p.x + fit.a * p.y + fit.ty,
    }))
    if (hasDegenerateCorners(moved)) {
      return null
    }
    const area = polyArea(moved)
    const frameArea = gray.cols * gray.rows
    if (area < frameArea * MIN_AREA_RATIO * 0.5 || area > frameArea * 0.95) {
      return null
    }
    // Survivor points become the next frame's seeds.
    const survivors = cv.matFromArray(
      to.length,
      1,
      cv.CV_32FC2,
      to.flatMap((p) => [p.x, p.y]),
    )
    trackPts.delete()
    trackPts = survivors
    trackQuad = moved
    return moved
  } catch {
    return null
  } finally {
    next.delete()
    status.delete()
    err.delete()
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
  if (d.t === 'detect') {
    if (!cv) {
      ;(self as any).postMessage({ t: 'nq' })
      return
    }
    // Shared grayscale for both the optical-flow step and point seeding.
    let gray: any = null
    try {
      const src = cv.matFromImageData(new ImageData(new Uint8ClampedArray(d.buf), d.w, d.h))
      gray = new cv.Mat()
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY)
      src.delete()
    } catch {
      gray = null
    }

    let frameQuad: { x: number; y: number }[] | null = null
    let tracking = false
    // A confident window match locks tracking onto that zone: the frame gets
    // glued to a hand-held card whose contours are unusable (fingers).
    if (gray && pendingLockRect) {
      const sx = d.w / d.vw
      const sy = d.h / d.vh
      const r = pendingLockRect
      pendingLockRect = null
      // La zone reçue est le crop d'identification gagnant, qui mord LÉGÈREMENT
      // dans la carte : gonfler de 8 % par côté pour que le cadre épouse les
      // bords de la carte plutôt que son intérieur.
      const gx = r.w * 0.08
      const gy = r.h * 0.08
      const lx = Math.max(0, (r.x - gx) * sx)
      const ly = Math.max(0, (r.y - gy) * sy)
      const lr = Math.min(d.w, (r.x + r.w + gx) * sx)
      const lb = Math.min(d.h, (r.y + r.h + gy) * sy)
      const lockQuad = [
        { x: lx, y: ly },
        { x: lr, y: ly },
        { x: lr, y: lb },
        { x: lx, y: lb },
      ]
      const seeds = seedTrackPoints(gray, lockQuad)
      if (seeds) {
        resetTrack()
        trackPts = seeds
        trackQuad = lockQuad
        trackW = d.w
        trackH = d.h
        trackFrames = 0
        frameQuad = lockQuad
        tracking = true
      }
    }
    if (!tracking && gray && trackQuad && trackGray && trackPts && trackW === d.w && trackH === d.h) {
      frameQuad = stepTrack(gray)
      tracking = frameQuad !== null
      trackFrames += 1
    }

    // Acquire (no track) or re-align (periodic) via contour detection.
    if (!tracking || trackFrames % TRACK_REDETECT_EVERY === 0) {
      let found = null
      try {
        found = detect(d.buf, d.w, d.h, d.vw, d.vh)
      } catch {
        found = null
      }
      if (found && gray) {
        const longEdge = Math.max(d.w, d.h)
        const dcx = (found.frame[0].x + found.frame[1].x + found.frame[2].x + found.frame[3].x) / 4
        const dcy = (found.frame[0].y + found.frame[1].y + found.frame[2].y + found.frame[3].y) / 4
        const tcx = frameQuad ? (frameQuad[0].x + frameQuad[1].x + frameQuad[2].x + frameQuad[3].x) / 4 : dcx
        const tcy = frameQuad ? (frameQuad[0].y + frameQuad[1].y + frameQuad[2].y + frameQuad[3].y) / 4 : dcy
        // Adopt the detection when there is no live track, or when it re-finds
        // the SAME card (close center) — never let a spurious far-away contour
        // steal a healthy track.
        if (!tracking || Math.hypot(dcx - tcx, dcy - tcy) < longEdge * 0.2) {
          const seeds = seedTrackPoints(gray, found.frame)
          if (seeds) {
            try {
              trackPts?.delete()
            } catch {}
            trackPts = seeds
            trackQuad = found.frame
            trackW = d.w
            trackH = d.h
            if (!tracking) {
              trackFrames = 0
            }
            frameQuad = found.frame
            tracking = true
          } else if (!tracking) {
            frameQuad = found.frame
          }
        }
      }
    } else if (tracking && gray && (trackFrames % TRACK_RESEED_EVERY === 0 || trackPts.rows < TRACK_RESEED_POINTS)) {
      const seeds = seedTrackPoints(gray, frameQuad!)
      if (seeds) {
        try {
          trackPts?.delete()
        } catch {}
        trackPts = seeds
      }
    }

    // Roll the grayscale forward for the next optical-flow step.
    if (gray && tracking) {
      try {
        trackGray?.delete()
      } catch {}
      trackGray = gray
      trackW = d.w
      trackH = d.h
    } else {
      if (!tracking) {
        resetTrack()
      }
      try {
        gray?.delete()
      } catch {}
    }

    // Continuous identification: ship one deskewed 224×224 crop to the main
    // thread (tracked quad first, else the sweeping windows). `d.im` lets the
    // main thread pause it (cooldown after a commit) so nothing competes with
    // the 20 fps tracking while the frame just needs to follow.
    try {
      if (d.im && Date.now() - lastIdCropAt >= ID_CROP_MIN_INTERVAL_MS) {
        lastIdCropAt = Date.now()
        shipIdentificationCrop(d.buf, d.w, d.h, d.vw, d.vh, frameQuad)
      }
    } catch {
      /* identification crop is best-effort — tracking must go on */
    }

    if (frameQuad) {
      const fx = d.vw / d.w
      const fy = d.vh / d.h
      const corners = frameQuad.map((p) => ({ x: p.x * fx, y: p.y * fy }))
      ;(self as any).postMessage({ t: 'quad', corners })
    } else {
      ;(self as any).postMessage({ t: 'nq' })
    }
    return
  }
  if (d.t === 'lock') {
    pendingLockRect = d.rect ?? null
    return
  }
  if (d.t === 'focus') {
    focusRect = d.rect ?? null
    focusUntil = Date.now() + FOCUS_TTL_MS
    return
  }
  if (d.t === 'droptrack') {
    // The main thread saw several identification misses on this quad — it is
    // probably framing furniture, not a card. Free the sweep and re-acquire.
    resetTrack()
    return
  }
}
