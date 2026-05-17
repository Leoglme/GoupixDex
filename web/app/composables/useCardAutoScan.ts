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
const STILL_EMA_MAX = 28
const STILL_EMA_ALPHA = 0.35
/** Brief motion when passing a card in front of the lens. */
const MOTION_ENTER_EMA_MIN = 32
const MOTION_ENTER_TICKS_REQUIRED = 2
/** Stable frames before capture (~0,6–0,8 s). */
const STILL_TICKS_REQUIRED = 5
/** Empty desk ≈ 3–5 ; card in frame ≈ 10+. */
const CONTENT_STDDEV_MIN = 7
/** Stddev jump vs empty-scene baseline ⇒ card just entered (tripod / no hand wave). */
const CONTENT_APPEAR_DELTA = 2.2
/** Stable frames with a card visible but no big motion (phone on a stand). */
const TRIPOD_STILL_TICKS = 7
const SCENE_LEAVE_DIFF = 9
const EMPTY_LEAVE_TICKS = 3
const MIN_COOLDOWN_MS = 2000
const MIN_REARM_MS = 2200
const BASELINE_STDDEV_ALPHA = 0.12

type ArmState = 'wait_pass' | 'settling' | 'wait_removal'

/**
 * Touch-free capture: fires when a card enters the frame (motion pass, contrast
 * jump, or held still on a stand) then stays sharp, then waits until removal.
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
  let motionEma = 0
  let baselineStddev = 4
  let stillTicks = 0
  let tripodStillTicks = 0
  let motionEnterTicks = 0
  let emptyLeaveTicks = 0
  let lastCaptureAt = 0
  let armState: ArmState = 'wait_pass'
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

  /** Reset motion counters when (re)arming for the next card pass. */
  function resetForNextPass(): void {
    prevGray = null
    motionEma = 0
    stillTicks = 0
    tripodStillTicks = 0
    motionEnterTicks = 0
    emptyLeaveTicks = 0
    armState = 'wait_pass'
    phase.value = 'watching'
  }

  /** Fire one capture and enter removal-wait state. */
  function tryCapture(gray: Float32Array): void {
    lastCaptureAt = Date.now()
    lastShotGray = gray.slice()
    stillTicks = 0
    tripodStillTicks = 0
    motionEnterTicks = 0
    motionEma = 0
    armState = 'wait_removal'
    emptyLeaveTicks = 0
    phase.value = 'captured'
    void Promise.resolve(onCapture()).finally(() => {
      phase.value = 'cooldown'
    })
  }

  /**
   * True when the captured card is no longer in frame (safe to scan the next one).
   *
   * @returns Whether the scene cleared enough to arm the next pass.
   */
  function cardHasLeftFrame(gray: Float32Array, stddev: number): boolean {
    if (stddev < CONTENT_STDDEV_MIN) {
      emptyLeaveTicks += 1
      return emptyLeaveTicks >= EMPTY_LEAVE_TICKS
    }
    emptyLeaveTicks = 0
    if (!lastShotGray) {
      return false
    }
    return frameDelta(gray, lastShotGray) >= SCENE_LEAVE_DIFF
  }

  /** One detector frame — never uploads unless a card entered and settled. */
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

    const prev = prevGray
    prevGray = gray
    if (prev) {
      const delta = frameDelta(gray, prev)
      motionEma = STILL_EMA_ALPHA * delta + (1 - STILL_EMA_ALPHA) * motionEma
    }

    if (busy.value) {
      return
    }

    if (armState === 'wait_removal') {
      phase.value = 'cooldown'
      const rearmDelayOk = Date.now() - lastCaptureAt >= MIN_REARM_MS
      if (rearmDelayOk && cardHasLeftFrame(gray, stddev)) {
        resetForNextPass()
      }
      return
    }

    const hasContent = stddev >= CONTENT_STDDEV_MIN
    const moving = motionEma > STILL_EMA_MAX

    if (!hasContent) {
      baselineStddev = BASELINE_STDDEV_ALPHA * stddev + (1 - BASELINE_STDDEV_ALPHA) * baselineStddev
    }

    if (armState === 'wait_pass') {
      phase.value = 'watching'
      if (!hasContent) {
        motionEnterTicks = 0
        tripodStillTicks = 0
        return
      }

      if (motionEma >= MOTION_ENTER_EMA_MIN) {
        motionEnterTicks += 1
      } else {
        motionEnterTicks = 0
      }

      if (!moving) {
        tripodStillTicks += 1
      } else {
        tripodStillTicks = 0
      }

      const contentAppeared = stddev - baselineStddev >= CONTENT_APPEAR_DELTA
      const motionPass = motionEnterTicks >= MOTION_ENTER_TICKS_REQUIRED
      const tripodReady = tripodStillTicks >= TRIPOD_STILL_TICKS

      if (contentAppeared || motionPass || tripodReady) {
        armState = 'settling'
        stillTicks = 0
        motionEnterTicks = 0
        tripodStillTicks = 0
      }
      return
    }

    // settling — card is in frame, wait until it stops moving
    if (!hasContent || moving) {
      stillTicks = 0
      phase.value = moving ? 'watching' : 'watching'
      if (!hasContent) {
        armState = 'wait_pass'
      }
      return
    }

    stillTicks += 1
    phase.value = 'settling'

    const settled = stillTicks >= STILL_TICKS_REQUIRED
    const canShoot = settled && Date.now() - lastCaptureAt >= MIN_COOLDOWN_MS

    if (canShoot) {
      tryCapture(gray)
    }
  }

  /** Start sampling frames from the video element. */
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

  /** Stop the frame sampling loop. */
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

  /** Start the detector loop. */
  function start(): void {
    stopLoop()
    lastCaptureAt = 0
    lastShotGray = null
    baselineStddev = 4
    resetForNextPass()
    scheduleLoop()
  }

  /** Stop the detector and release canvas resources. */
  function stop(): void {
    stopLoop()
    canvas = null
    ctx = null
    lastShotGray = null
    armState = 'wait_pass'
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
