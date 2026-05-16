import type { Ref } from 'vue'

/**
 * Auto-scan state, surfaced to the UI so the user knows what the camera is
 * doing without any button:
 * - `idle`      : detector stopped (camera off / disabled)
 * - `watching`  : waiting for a card to enter the frame
 * - `settling`  : a card moved in, waiting for it to be held still
 * - `captured`  : a stable card was just shot and sent
 * - `cooldown`  : waiting for the card to leave before arming the next one
 */
export type AutoScanPhase = 'idle' | 'watching' | 'settling' | 'captured' | 'cooldown'

export interface UseCardAutoScanOptions {
  /** Live preview element the frames are sampled from. */
  video: Ref<HTMLVideoElement | null>
  /** Master switch — detector only runs while this is `true`. */
  enabled: Ref<boolean>
  /** `true` while an upload is in flight; we never fire a capture then. */
  busy: Ref<boolean>
  /** Called once per stable card. Should trigger the capture + upload. */
  onCapture: () => void | Promise<void>
}

/** ~4.5 samples / second — responsive without burning the main thread. */
const SAMPLE_MS = 220
/** Long edge of the downscaled analysis buffer (grayscale, ~card ratio). */
const SAMPLE_W = 80
const SAMPLE_H = 112
/** Mean abs frame delta (0–255) that counts as "something moved". */
const MOTION_DIFF = 8
/** Frame delta below which the scene is considered "held still". */
const STILL_DIFF = 2.6
/** Consecutive still samples required before firing (~0.66 s). */
const STILL_HITS = 3
/** Min grayscale stddev so a blank background never triggers a capture. */
const CONTENT_STDDEV_MIN = 10
/** Floor between two captures, guards against micro-jitter double shots. */
const MIN_COOLDOWN_MS = 1200

/**
 * Touch-free "cash register" capture: watch the live camera, and the instant a
 * card is placed and held steady, fire `onCapture` once. The next shot only
 * arms after the scene changes again (card removed / swapped), so a single
 * card is never scanned twice.
 *
 * Pure frame-difference heuristics (no ML, no extra deps): a capture needs a
 * motion spike (card arriving) followed by a run of still, content-rich frames.
 *
 * @param opts - Preview element, enable flag, busy flag and capture callback.
 * @returns Reactive `phase` for UI feedback.
 */
export function useCardAutoScan(opts: UseCardAutoScanOptions) {
  const { video, enabled, busy, onCapture } = opts

  const phase: Ref<AutoScanPhase> = ref('idle')

  let timer: ReturnType<typeof setInterval> | null = null
  let canvas: HTMLCanvasElement | null = null
  let ctx: CanvasRenderingContext2D | null = null
  let prevGray: Float32Array | null = null
  let stillRun = 0
  let sawMotion = false
  let lastCaptureAt = 0

  /**
   * Grayscale (luma) + stddev of the current downscaled frame.
   * @returns Sample, or `null` when the video isn't drawable yet.
   */
  function sampleFrame(): { gray: Float32Array; stddev: number } | null {
    const el = video.value
    if (!el || !el.videoWidth || !el.videoHeight) {
      return null
    }
    if (!canvas) {
      canvas = document.createElement('canvas')
      canvas.width = SAMPLE_W
      canvas.height = SAMPLE_H
      ctx = canvas.getContext('2d', { willReadFrequently: true })
    }
    if (!ctx) {
      return null
    }
    ctx.drawImage(el, 0, 0, SAMPLE_W, SAMPLE_H)
    const { data } = ctx.getImageData(0, 0, SAMPLE_W, SAMPLE_H)
    const n = SAMPLE_W * SAMPLE_H
    const gray = new Float32Array(n)
    let sum = 0
    for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
      const lum = 0.299 * data[i]! + 0.587 * data[i + 1]! + 0.114 * data[i + 2]!
      gray[p] = lum
      sum += lum
    }
    const mean = sum / n
    let varAcc = 0
    for (let p = 0; p < n; p += 1) {
      const d = gray[p]! - mean
      varAcc += d * d
    }
    return { gray, stddev: Math.sqrt(varAcc / n) }
  }

  /**
   * Mean absolute luma delta between two equal-length frames.
   * @param a - Current frame luma buffer.
   * @param b - Previous frame luma buffer.
   * @returns Average per-pixel absolute difference (0–255).
   */
  function frameDelta(a: Float32Array, b: Float32Array): number {
    let acc = 0
    for (let i = 0; i < a.length; i += 1) {
      acc += Math.abs(a[i]! - b[i]!)
    }
    return acc / a.length
  }

  /**
   *
   */
  function resetCycle(): void {
    prevGray = null
    stillRun = 0
    sawMotion = false
  }

  /**
   *
   */
  function tick(): void {
    if (!enabled.value) {
      return
    }
    const sample = sampleFrame()
    if (!sample) {
      return
    }
    const { gray, stddev } = sample
    const prev = prevGray
    prevGray = gray
    if (!prev) {
      return
    }
    const delta = frameDelta(gray, prev)

    if (phase.value === 'cooldown') {
      // Wait for the card to leave / be swapped before arming again.
      if (delta >= MOTION_DIFF && Date.now() - lastCaptureAt >= MIN_COOLDOWN_MS) {
        resetCycle()
        phase.value = 'watching'
      }
      return
    }

    if (delta >= MOTION_DIFF) {
      sawMotion = true
      stillRun = 0
      phase.value = 'settling'
      return
    }

    if (!sawMotion) {
      phase.value = 'watching'
      return
    }

    // A card arrived and the frame is now calm — accumulate still samples.
    if (delta <= STILL_DIFF && stddev >= CONTENT_STDDEV_MIN) {
      stillRun += 1
      phase.value = 'settling'
      if (stillRun >= STILL_HITS && !busy.value && Date.now() - lastCaptureAt >= MIN_COOLDOWN_MS) {
        lastCaptureAt = Date.now()
        stillRun = 0
        sawMotion = false
        phase.value = 'captured'
        void Promise.resolve(onCapture()).finally(() => {
          phase.value = 'cooldown'
        })
      }
      return
    }
    stillRun = 0
  }

  /**
   *
   */
  function start(): void {
    if (timer !== null) {
      return
    }
    resetCycle()
    lastCaptureAt = 0
    phase.value = 'watching'
    timer = setInterval(tick, SAMPLE_MS)
  }

  /**
   *
   */
  function stop(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    canvas = null
    ctx = null
    resetCycle()
    phase.value = 'idle'
  }

  watch(
    enabled,
    (on) => {
      if (on) {
        start()
      } else {
        stop()
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(stop)

  return { phase }
}
