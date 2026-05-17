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

/** ~8 samples / second when `requestVideoFrameCallback` is available. */
const SAMPLE_MS = 125
const SAMPLE_W = 96
const SAMPLE_H = 134
/** Center crop ratio — ignore desk edges that add false motion. */
const CROP_RATIO = 0.72
/**
 * EMA of frame delta above this ⇒ "moving". High on purpose: phone AE flicker
 * often sits at 12–25 even on a tripod.
 */
const STILL_EMA_MAX = 28
const STILL_EMA_ALPHA = 0.35
/** EMA must stay below threshold for this many ticks before capture. */
const STILL_TICKS_REQUIRED = 5
/** Min contrast in the center crop (empty desk ≈ 3–5, card ≈ 12+). */
const CONTENT_STDDEV_MIN = 5
/** Ignore re-shooting the same card until the scene changes this much. */
const SCENE_CHANGE_DIFF = 4
const MIN_COOLDOWN_MS = 1100
/** After camera ready, force one capture if nothing fired (tripod / card already in frame). */
const FORCE_CAPTURE_AFTER_MS = 2800

/**
 * Touch-free "cash register" capture: sample the live camera, detect a card-like
 * center region, and fire `onCapture` when motion settles (EMA) or after a short
 * timeout if the card was already in frame.
 *
 * @param opts - Preview element, enable flag, busy flag and capture callback.
 * @returns Reactive `phase` for UI feedback.
 */
export function useCardAutoScan(opts: UseCardAutoScanOptions) {
  const { video, enabled, busy, onCapture } = opts

  const phase: Ref<AutoScanPhase> = ref('idle')

  let canvas: HTMLCanvasElement | null = null
  let ctx: CanvasRenderingContext2D | null = null
  let prevGray: Float32Array | null = null
  let lastShotGray: Float32Array | null = null
  let motionEma = 99
  let stillTicks = 0
  let lastCaptureAt = 0
  let readySince = 0
  let rafId: number | null = null
  let intervalId: ReturnType<typeof setInterval> | null = null

  /**
   * Downsample the central crop of the current video frame for motion detection.
   *
   * @returns Grayscale sample and luminance stddev, or `null` if the video is not ready.
   */
  function sampleFrame(): { gray: Float32Array; stddev: number } | null {
    const el = video.value
    if (!el || el.readyState < 2 || !el.videoWidth || !el.videoHeight) {
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

    const vw = el.videoWidth
    const vh = el.videoHeight
    const cw = vw * CROP_RATIO
    const ch = vh * CROP_RATIO
    const sx = (vw - cw) / 2
    const sy = (vh - ch) / 2

    ctx.drawImage(el, sx, sy, cw, ch, 0, 0, SAMPLE_W, SAMPLE_H)
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
   * Mean absolute difference between two grayscale frames (0 = identical).
   *
   * @returns Average per-pixel luminance delta.
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
    motionEma = 99
    stillTicks = 0
    readySince = Date.now()
  }

  /**
   *
   */
  function tryCapture(gray: Float32Array): void {
    lastCaptureAt = Date.now()
    lastShotGray = gray.slice()
    stillTicks = 0
    motionEma = 99
    phase.value = 'captured'
    void Promise.resolve(onCapture()).finally(() => {
      phase.value = 'cooldown'
    })
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
      phase.value = 'watching'
      return
    }
    const { gray, stddev } = sample

    if (stddev < CONTENT_STDDEV_MIN) {
      stillTicks = 0
      motionEma = 99
      phase.value = 'watching'
      prevGray = gray
      return
    }

    const prev = prevGray
    prevGray = gray
    if (prev) {
      const delta = frameDelta(gray, prev)
      motionEma = STILL_EMA_ALPHA * delta + (1 - STILL_EMA_ALPHA) * motionEma
    }

    const moving = motionEma > STILL_EMA_MAX
    if (moving) {
      stillTicks = 0
      phase.value = 'watching'
      return
    }
    stillTicks += 1

    if (lastShotGray && frameDelta(gray, lastShotGray) < SCENE_CHANGE_DIFF) {
      phase.value = 'cooldown'
      return
    }

    const settled = stillTicks >= STILL_TICKS_REQUIRED
    const forceByTime = readySince > 0 && Date.now() - readySince >= FORCE_CAPTURE_AFTER_MS && !lastShotGray
    const canShoot = !busy.value && Date.now() - lastCaptureAt >= MIN_COOLDOWN_MS

    if (canShoot && (settled || forceByTime)) {
      tryCapture(gray)
      return
    }

    phase.value = 'settling'
  }

  /**
   *
   */
  function scheduleLoop(): void {
    const el = video.value
    if (el && typeof el.requestVideoFrameCallback === 'function') {
      const onFrame = (): void => {
        if (!enabled.value) {
          return
        }
        tick()
        rafId = el.requestVideoFrameCallback(onFrame)
      }
      rafId = el.requestVideoFrameCallback(onFrame)
      return
    }
    intervalId = setInterval(tick, SAMPLE_MS)
  }

  /**
   *
   */
  function stopLoop(): void {
    const el = video.value
    if (rafId !== null && el && typeof el.cancelVideoFrameCallback === 'function') {
      el.cancelVideoFrameCallback(rafId)
    }
    rafId = null
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  /**
   *
   */
  function start(): void {
    stopLoop()
    resetCycle()
    lastCaptureAt = 0
    lastShotGray = null
    phase.value = 'watching'
    scheduleLoop()
  }

  /**
   *
   */
  function stop(): void {
    stopLoop()
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

  watch(
    () => video.value,
    () => {
      if (enabled.value) {
        stop()
        start()
      }
    },
  )

  onBeforeUnmount(stop)

  return { phase }
}
