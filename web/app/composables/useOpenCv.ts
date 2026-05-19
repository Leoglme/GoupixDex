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
    let done = false

    const finish = (): boolean => {
      const cv = w.cv
      if (done || !cv || typeof cv.Mat !== 'function') {
        return false
      }
      done = true
      resolve(cv)
      return true
    }

    // The docs.opencv.org build exposes a global `cv` that is an Emscripten
    // Module: its `then` is NOT a real Promise (no `.catch`), and `cv.Mat`
    // only appears once the wasm runtime is initialised. We hook every signal
    // and, crucially, poll as a safety net so the promise ALWAYS settles
    // (otherwise the page hangs forever on "chargement du moteur").
    let wired = false
    const wire = (): void => {
      const cv = w.cv
      if (!cv || wired) {
        return
      }
      wired = true
      try {
        if (typeof cv.then === 'function') {
          cv.then((m: Cv) => {
            if (m && typeof m.Mat === 'function') {
              w.cv = m
            }
            finish()
          })
        }
      } catch {
        /* Emscripten thenable can throw if called twice — ignored. */
      }
      cv.onRuntimeInitialized = (): void => {
        finish()
      }
    }

    let tries = 0
    const poll = window.setInterval(() => {
      tries += 1
      wire()
      if (finish()) {
        window.clearInterval(poll)
      } else if (tries >= 300) {
        // ~30 s
        window.clearInterval(poll)
        if (!done) {
          done = true
          reject(new Error('OpenCV: délai d’initialisation dépassé'))
        }
      }
    }, 100)

    if (w.cv) {
      wire()
      return
    }
    const existing = document.getElementById('opencv-js') as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', wire)
      existing.addEventListener('error', () => {
        window.clearInterval(poll)
        if (!done) {
          done = true
          reject(new Error('OpenCV failed to load'))
        }
      })
      return
    }
    const s = document.createElement('script')
    s.id = 'opencv-js'
    s.async = true
    s.src = OPENCV_URL
    s.onload = wire
    s.onerror = (): void => {
      window.clearInterval(poll)
      if (!done) {
        done = true
        reject(new Error('OpenCV failed to load'))
      }
    }
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
