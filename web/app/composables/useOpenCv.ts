/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Lazy OpenCV.js loader. The wasm build is ~8 MB so it is fetched **only** on
 * the scan page, on demand, and cached by the browser afterwards. Self-host by
 * dropping `opencv.js` in `web/public/opencv/` and pointing `OPENCV_URL` there.
 */

/** Where opencv.js is fetched from (official 4.x build; override to self-host). */
export const OPENCV_URL = 'https://docs.opencv.org/4.10.0/opencv.js'

/** The handful of OpenCV symbols this app touches (kept loose on purpose). */
export type Cv = any

let cvPromise: Promise<Cv> | null = null

/**
 * Load (once) and resolve the global OpenCV module after its wasm runtime is
 * initialised. Concurrent callers share the same promise.
 *
 * @returns Promise resolving to the ready `cv` module.
 */
export function loadOpenCv(): Promise<Cv> {
  if (cvPromise) {
    return cvPromise
  }
  cvPromise = new Promise<Cv>((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error('OpenCV not available server-side'))
      return
    }
    const w = window as unknown as { cv?: any }

    const settle = (): void => {
      const cv = w.cv
      if (!cv) {
        reject(new Error('OpenCV global missing after load'))
        return
      }
      if (typeof cv.then === 'function') {
        // Newer emscripten builds export a module factory promise.
        cv.then((m: Cv) => {
          w.cv = m
          resolve(m)
        }).catch(reject)
        return
      }
      if (cv.Mat) {
        resolve(cv)
        return
      }
      cv.onRuntimeInitialized = (): void => resolve(w.cv)
    }

    if (w.cv) {
      settle()
      return
    }
    const existing = document.getElementById('opencv-js') as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', settle)
      existing.addEventListener('error', () => reject(new Error('OpenCV failed to load')))
      return
    }
    const s = document.createElement('script')
    s.id = 'opencv-js'
    s.async = true
    s.src = OPENCV_URL
    s.onload = settle
    s.onerror = (): void => reject(new Error('OpenCV failed to load'))
    document.head.appendChild(s)
  })
  return cvPromise
}

/**
 * Composable wrapper so pages can `const { load } = useOpenCv()`.
 * @returns `{ load }` — call `load()` to get the ready `cv` module.
 */
export function useOpenCv() {
  return { load: loadOpenCv }
}
