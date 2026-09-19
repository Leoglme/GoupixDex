import type { ComputedRef, Ref } from 'vue'
import type { ScanCardLanguage, ScanIdentifyResult } from '~/types/ScanMatch'

const ORT_UMD_URL = '/ort/ort.wasm.min.js'
const ORT_WASM_BASE = '/ort/'

/** Réponse au-delà de ce délai = worker mort → la tentative est abandonnée. */
const IDENTIFY_TIMEOUT_MS = 15000

const EMPTY_RESULT: ScanIdentifyResult = { decision: null, topCardId: null, topSim: 0, topMargin: 0, bestCropIndex: 0 }

type IdentifierWorkerReply =
  | { t: 'ready' }
  | { t: 'init-error'; message: string }
  | { t: 'result'; seq: number; result: ScanIdentifyResult }

let worker: Worker | null = null
let workerReadyPromise: Promise<void> | null = null
let identifySeq = 0
const pendingIdentifies: Map<number, (result: ScanIdentifyResult) => void> = new Map()

/**
 * Démarre le worker d'identification (une fois par session) et attend son
 * chargement complet : onnxruntime + modèle + index + PCA vivent dans le
 * worker — l'inférence gelait l'interface quand elle tournait sur le main
 * thread (0,5-1 s par tentative sur téléphone).
 * @returns {Promise<void>} Résolue quand le worker est prêt, rejetée sinon.
 */
function startWorkerOnce(): Promise<void> {
  if (!workerReadyPromise) {
    workerReadyPromise = new Promise<void>((resolve, reject) => {
      if (typeof Worker === 'undefined') {
        reject(new Error('workers non supportés'))
        return
      }
      try {
        worker = new Worker(new URL('../workers/cardIdentifier.worker.ts', import.meta.url))
      } catch (err) {
        reject(err instanceof Error ? err : new Error(String(err)))
        return
      }
      worker.onerror = (): void => {
        reject(new Error('worker identification indisponible'))
      }
      worker.onmessage = (e: MessageEvent<IdentifierWorkerReply>): void => {
        const d = e.data
        if (d.t === 'ready') {
          resolve()
          return
        }
        if (d.t === 'init-error') {
          reject(new Error(d.message))
          return
        }
        if (d.t === 'result') {
          const settle = pendingIdentifies.get(d.seq)
          if (settle) {
            pendingIdentifies.delete(d.seq)
            settle(d.result)
          }
        }
      }
      worker.postMessage({
        t: 'init',
        ortUrl: ORT_UMD_URL,
        wasmBase: ORT_WASM_BASE,
        s0ModelUrl: '/scan-model/mobileclip-s0-vision-fp16.onnx',
        s0BinUrl: '/scan-index/embed-v3.bin',
        s0JsonUrl: '/scan-index/embed-v3.json',
        mnetModelUrl: '/scan-model/mobilenet-embed-int8.onnx',
        mnetBinUrl: '/scan-index/embed-v2.bin',
        mnetPcaUrl: '/scan-index/embed-pca-v2.bin',
        mnetJsonUrl: '/scan-index/embed-v2.json',
      })
    })
    workerReadyPromise.catch((): void => {
      workerReadyPromise = null
    })
  }
  return workerReadyPromise
}

/**
 * Identification visuelle DOUBLE ESPACE : MobileCLIP-S0 (robuste lumière
 * naturelle / foil) + MobileNetV2 (fidèle à l'artwork exact), chacun avec sa
 * politique, matchés en cosinus contre les ~44k images TCGdex dans un worker
 * dédié (voir `app/workers/cardIdentifier.worker.ts` et
 * `api/scripts/build_scan_embed_index{,_v3}.py`).
 * @returns {object} État de chargement, `load()` et `identify()`.
 */
export function useScanEmbedIndex() {
  const isReady: Ref<boolean> = ref(false)
  const loadFailed: Ref<boolean> = ref(false)
  const ready: ComputedRef<boolean> = computed(() => isReady.value)

  /**
   * Charge le worker d'identification (idempotent). Un échec laisse le
   * scanner en mode photo-OCR serveur — jamais bloquant.
   * @returns {Promise<void>} Résolue une fois le chargement terminé (ou l'échec acté).
   */
  async function load(): Promise<void> {
    if (isReady.value) {
      return
    }
    try {
      await startWorkerOnce()
      isReady.value = true
      loadFailed.value = false
    } catch {
      loadFailed.value = true
    }
  }

  /**
   * Identifie une tentative (1 à 6 crops RGBA 256×256) via le worker — les
   * buffers sont TRANSFÉRÉS (non copiés) et deviennent inutilisables ensuite.
   * @param crops - Crops RGBA 256×256 de la tentative.
   * @param sessionLanguage - Langue de session (`auto` = locale du meilleur print).
   * @returns {Promise<ScanIdentifyResult>} Décision sûre éventuelle + meilleur hit brut
   *   (sert à la recherche focalisée, au cadre précoce et au recalage en cooldown).
   */
  async function identify(crops: Uint8ClampedArray[], sessionLanguage: ScanCardLanguage): Promise<ScanIdentifyResult> {
    if (!worker || !isReady.value || crops.length === 0) {
      return EMPTY_RESULT
    }
    identifySeq += 1
    const seq = identifySeq
    const bufs = crops.map((c: Uint8ClampedArray): ArrayBuffer => c.buffer as ArrayBuffer)
    return new Promise<ScanIdentifyResult>((resolve) => {
      const timeout = setTimeout((): void => {
        pendingIdentifies.delete(seq)
        resolve(EMPTY_RESULT)
      }, IDENTIFY_TIMEOUT_MS)
      pendingIdentifies.set(seq, (result: ScanIdentifyResult): void => {
        clearTimeout(timeout)
        resolve(result)
      })
      worker!.postMessage({ t: 'identify', seq, bufs, language: sessionLanguage }, bufs)
    })
  }

  return { ready, loadFailed, load, identify }
}
