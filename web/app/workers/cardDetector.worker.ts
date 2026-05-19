/* eslint-disable */
// @ts-nocheck
/**
 * Card-detection Web Worker. OpenCV.js (~9 MB + wasm) is loaded and run here so
 * the heavy contour/perspective work NEVER blocks the UI thread.
 *
 * Frames arrive as raw RGBA buffers (the main thread draws the <video> to a
 * plain 2D canvas — no `createImageBitmap`/OffscreenCanvas, both flaky on iOS).
 *
 * Protocol (main ⇄ worker):
 *   → { t:'init', url }                              ← { t:'ready' } | { t:'error', m }
 *   → { t:'detect', buf, w, h, vw, vh }              ← { t:'quad', corners } | { t:'nq' }
 *   → { t:'warp', buf, w, h, corners }               ← { t:'warped', buf, w, h } | { t:'error', m }
 *
 * `corners` are always VIDEO-intrinsic pixel coords.
 */

const MIN_AREA_RATIO = 0.1 // card must cover ≥10% of the frame
const MAX_FILL = 0.97 // reject "the whole frame" (camera border / vignette)
const AR_MIN = 1.05 // card ≈ 88/63 ≈ 1.40; generous for perspective tilt
const AR_MAX = 2.6
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

/**
 * Find the card outline. Strategy: close the edge map aggressively, take the
 * LARGEST external contour, and use its 4-point polygon if it has one, else
 * its min-area rotated rectangle. That tracks a real (rounded-corner, glary,
 * partly hand-occluded) card instead of demanding a perfect quad.
 */
function detect(buf: ArrayBuffer, w: number, h: number, vw: number, vh: number) {
  const img = new ImageData(new Uint8ClampedArray(buf), w, h)
  const src = cv.matFromImageData(img)
  const gray = new cv.Mat()
  const edges = new cv.Mat()
  const contours = new cv.MatVector()
  const hierarchy = new cv.Mat()
  let chosen: { x: number; y: number }[] | null = null
  try {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY)
    cv.GaussianBlur(gray, gray, new cv.Size(5, 5), 0, 0, cv.BORDER_DEFAULT)
    cv.Canny(gray, edges, 45, 140)
    const k = cv.Mat.ones(7, 7, cv.CV_8U)
    cv.morphologyEx(edges, edges, cv.MORPH_CLOSE, k)
    cv.dilate(edges, edges, k)
    k.delete()
    cv.findContours(edges, contours, hierarchy, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)

    const frameArea = w * h
    let bestCnt: any = null
    let bestArea = 0
    for (let i = 0; i < contours.size(); i += 1) {
      const cnt = contours.get(i)
      const area = cv.contourArea(cnt)
      if (area > bestArea) {
        if (bestCnt) {
          bestCnt.delete()
        }
        bestArea = area
        bestCnt = cnt
      } else {
        cnt.delete()
      }
    }

    if (bestCnt && bestArea >= frameArea * MIN_AREA_RATIO) {
      let pts: { x: number; y: number }[] | null = null
      const peri = cv.arcLength(bestCnt, true)
      const approx = new cv.Mat()
      cv.approxPolyDP(bestCnt, approx, 0.02 * peri, true)
      if (approx.rows === 4 && cv.isContourConvex(approx)) {
        pts = []
        for (let r = 0; r < 4; r += 1) {
          pts.push({ x: approx.intPtr(r, 0)[0], y: approx.intPtr(r, 0)[1] })
        }
      } else {
        pts = rrCorners(cv.minAreaRect(bestCnt))
      }
      approx.delete()

      const ordered = orderCorners(pts)
      const fill = polyArea(ordered) / frameArea
      const wEdge = Math.hypot(ordered[1].x - ordered[0].x, ordered[1].y - ordered[0].y)
      const hEdge = Math.hypot(ordered[3].x - ordered[0].x, ordered[3].y - ordered[0].y)
      const ar = Math.max(wEdge, hEdge) / Math.max(1, Math.min(wEdge, hEdge))
      if (fill <= MAX_FILL && ar >= AR_MIN && ar <= AR_MAX) {
        const fx = vw / w
        const fy = vh / h
        chosen = ordered.map((p) => ({ x: p.x * fx, y: p.y * fy }))
      }
    }
    if (bestCnt) {
      bestCnt.delete()
    }
  } catch {
    chosen = null
  } finally {
    src.delete()
    gray.delete()
    edges.delete()
    contours.delete()
    hierarchy.delete()
  }
  return chosen
}

/** Perspective-deskew the card → raw RGBA (main thread encodes the JPEG). */
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
  try {
    const M = cv.getPerspectiveTransform(srcTri, dstTri)
    cv.warpPerspective(src, dst, M, new cv.Size(WARP_W, WARP_H), cv.INTER_LINEAR, cv.BORDER_CONSTANT, new cv.Scalar())
    M.delete()
    return new Uint8ClampedArray(dst.data).buffer
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
      const out = warp(d.buf, d.w, d.h, d.corners)
      ;(self as any).postMessage({ t: 'warped', buf: out, w: WARP_W, h: WARP_H }, [out])
    } catch {
      ;(self as any).postMessage({ t: 'error', m: 'Découpe carte impossible' })
    }
    return
  }
}
