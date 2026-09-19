import type { ComputedRef, Ref } from 'vue'
import type { ScanCardLanguage, ScanPhashResult } from '~/types/ScanMatch'

/** Réponse au-delà de ce délai = worker mort, la tentative est abandonnée. */
const MATCH_TIMEOUT_MS = 8000

const EMPTY_RESULT: ScanPhashResult = { status: 'none', decision: null, score: 1 }

type PhashWorkerReply =
  | { t: 'ready' }
  | { t: 'init-error'; message: string }
  | { t: 'result'; seq: number; result: ScanPhashResult }

let worker: Worker | null = null
let workerReadyPromise: Promise<void> | null = null
let matchSeq = 0
const pendingMatches: Map<number, (result: ScanPhashResult) => void> = new Map()

/**
 * Démarre le worker pHash (une fois par session) : il charge l'index binaire
 * d'empreintes perceptuelles (94k cartes 6 langues, sets JA récents inclus) et
 * matche par distance de Hamming — instantané, et REFUSE au lieu de deviner.
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
        worker = new Worker(new URL('../workers/cardPhash.worker.ts', import.meta.url))
      } catch (err) {
        reject(err instanceof Error ? err : new Error(String(err)))
        return
      }
      worker.onerror = (): void => {
        reject(new Error('worker pHash indisponible'))
      }
      worker.onmessage = (e: MessageEvent<PhashWorkerReply>): void => {
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
          const settle = pendingMatches.get(d.seq)
          if (settle) {
            pendingMatches.delete(d.seq)
            settle(d.result)
          }
        }
      }
      worker.postMessage({
        t: 'init',
        binUrl: '/scan-index/phash-v1.bin',
        jsonUrl: '/scan-index/phash-v1.json',
      })
    })
    workerReadyPromise.catch((): void => {
      workerReadyPromise = null
    })
  }
  return workerReadyPromise
}

/**
 * Matcher d'identification par EMPREINTE PERCEPTUELLE (pHash de l'artwork),
 * complémentaire de l'embedding neuronal : instantané, couvre les cartes JA
 * récentes absentes de l'index d'embeddings, et refuse quand rien ne colle
 * (voir `app/workers/cardPhash.worker.ts` et `api/scripts/build_phash_index.py`).
 * @returns {object} État de chargement, `load()` et `match()`.
 */
export function useScanPhash() {
  const isReady: Ref<boolean> = ref(false)
  const loadFailed: Ref<boolean> = ref(false)
  const ready: ComputedRef<boolean> = computed(() => isReady.value)

  /**
   * Charge le worker pHash (idempotent). Un échec laisse le scanner sur le seul
   * embedding — jamais bloquant.
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
   * Matche une carte REDRESSÉE (RGBA `w`×`h`, warp du quad par le détecteur) —
   * le buffer est TRANSFÉRÉ (non copié) et devient inutilisable ensuite.
   * @param buf - RGBA de la carte redressée.
   * @param w - Largeur du crop.
   * @param h - Hauteur du crop.
   * @param language - Langue de session (préférée quand la carte existe dans plusieurs langues).
   * @returns {Promise<ScanPhashResult>} Décision sûre éventuelle + score.
   */
  async function match(buf: ArrayBuffer, w: number, h: number, language: ScanCardLanguage): Promise<ScanPhashResult> {
    if (!worker || !isReady.value) {
      return EMPTY_RESULT
    }
    matchSeq += 1
    const seq = matchSeq
    return new Promise<ScanPhashResult>((resolve) => {
      const timeout = setTimeout((): void => {
        pendingMatches.delete(seq)
        resolve(EMPTY_RESULT)
      }, MATCH_TIMEOUT_MS)
      pendingMatches.set(seq, (result: ScanPhashResult): void => {
        clearTimeout(timeout)
        resolve(result)
      })
      worker!.postMessage({ t: 'match', seq, buf, w, h, language }, [buf])
    })
  }

  return { ready, loadFailed, load, match }
}
