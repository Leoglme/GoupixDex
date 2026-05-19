/* eslint-disable */
// @ts-nocheck
/**
 * Card-detection Web Worker. OpenCV.js (~9 MB + wasm) is loaded and run here so
 * the heavy contour/perspective work NEVER blocks the UI thread (the bug:
 * loading it on the main thread froze the phone on "Chargement du moteur").
 *
 * Protocol (main ⇄ worker):
 *   → { t:'init', url }                         ← { t:'ready' } | { t:'error', m }
 *   → { t:'detect', bmp, vw, vh }               ← { t:'quad', corners } | { t:'nq' }
 *   → { t:'warp', bmp, vw, vh, corners }        ← { t:'warped', buf } | { t:'error', m }
 *
 * `corners` are always in VIDEO-intrinsic pixel coords (main thread just draws
 * / uploads them; all OpenCV math stays here).
 */

const PROC_EDGE = 480
const MIN_AREA_RATIO = 0.14
const WARP_W = 630
const WARP_H = 880

let cv: any = null
let off: OffscreenCanvas | null = null
let octx: OffscreenCanvasRenderingContext2D | null = null

function ensureCanvas(w: number, h: number): OffscreenCanvasRenderingContext2D | null {
  if (!off || off.width !== w || off.height !== h) {
    off = new OffscreenCanvas(w, h)
    octx = off.getContext('2d', { willReadFrequently: true }) as OffscreenCanvasRenderingContext2D | null
  }
  return octx
}

function orderCorners(pts: { x: number; y: number }[]): { x: number; y: number }[] {
  const bySum = [...pts].sort((a, b) => a.x + a.y - (b.x + b.y))
  const byDiff = [...pts].sort((a, b) => a.y - a.x - (b.y - b.x))
  return [bySum[0], byDiff[0], bySum[3], byDiff[3]]
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
      } catch {
        /* emscripten thenable quirk */
      }
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

/** Detect the largest convex card quad; returns ordered video-px corners. */
function detect(bmp: ImageBitmap, vw: number, vh: number): { x: number; y: number }[] | null {
  const scale = PROC_EDGE / Math.max(vw, vh)
  const pw = Math.max(1, Math.round(vw * scale))
  const ph = Math.max(1, Math.round(vh * scale))
  const ctx = ensureCanvas(pw, ph)
  if (!ctx) {
    return null
  }
  ctx.drawImage(bmp, 0, 0, pw, ph)
  const src = cv.matFromImageData(ctx.getImageData(0, 0, pw, ph))
  const gray = new cv.Mat()
  const edges = new cv.Mat()
  const contours = new cv.MatVector()
  const hierarchy = new cv.Mat()
  let best: { corners: { x: number; y: number }[]; area: number } | null = null
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
        const c: { x: number; y: number }[] = []
        for (let r = 0; r < 4; r += 1) {
          c.push({ x: approx.intPtr(r, 0)[0], y: approx.intPtr(r, 0)[1] })
        }
        if (!best || area > best.area) {
          best = { corners: orderCorners(c), area }
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
  if (!best) {
    return null
  }
  const fx = vw / pw
  const fy = vh / ph
  return best.corners.map((p) => ({ x: p.x * fx, y: p.y * fy }))
}

/** Perspective-deskew the card from a full-res bitmap → JPEG ArrayBuffer. */
async function warp(
  bmp: ImageBitmap,
  vw: number,
  vh: number,
  corners: { x: number; y: number }[],
): Promise<ArrayBuffer> {
  const work = new OffscreenCanvas(vw, vh)
  const wctx = work.getContext('2d') as OffscreenCanvasRenderingContext2D
  wctx.drawImage(bmp, 0, 0, vw, vh)
  const src = cv.matFromImageData(wctx.getImageData(0, 0, vw, vh))
  const dst = new cv.Mat()
  const srcTri = cv.matFromArray(
    4,
    1,
    cv.CV_32FC2,
    corners.flatMap((p) => [p.x, p.y]),
  )
  const dstTri = cv.matFromArray(4, 1, cv.CV_32FC2, [0, 0, WARP_W, 0, WARP_W, WARP_H, 0, WARP_H])
  try {
    const M = cv.getPerspectiveTransform(srcTri, dstTri)
    cv.warpPerspective(src, dst, M, new cv.Size(WARP_W, WARP_H), cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar())
    M.delete()
    const outCtx = ensureCanvas(WARP_W, WARP_H)!
    const img = new ImageData(new Uint8ClampedArray(dst.data), WARP_W, WARP_H)
    outCtx.putImageData(img, 0, 0)
    const blob = await off!.convertToBlob({ type: 'image/jpeg', quality: 0.92 })
    return await blob.arrayBuffer()
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
    } catch (err) {
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
    if (d.bmp) {
      d.bmp.close?.()
    }
    return
  }
  if (d.t === 'detect') {
    let corners: { x: number; y: number }[] | null = null
    try {
      corners = detect(d.bmp, d.vw, d.vh)
    } catch {
      corners = null
    } finally {
      d.bmp.close?.()
    }
    ;(self as any).postMessage(corners ? { t: 'quad', corners } : { t: 'nq' })
    return
  }
  if (d.t === 'warp') {
    warp(d.bmp, d.vw, d.vh, d.corners)
      .then((buf) => (self as any).postMessage({ t: 'warped', buf }, [buf]))
      .catch(() => (self as any).postMessage({ t: 'error', m: 'Découpe carte impossible' }))
      .finally(() => d.bmp.close?.())
    return
  }
}
