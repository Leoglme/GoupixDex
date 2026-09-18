import type { ComputedRef, Ref } from 'vue'
import type { ScanCardLanguage, ScanMatchCard, ScanMatchDecision } from '~/types/ScanMatch'

const INDEX_VERSION = 1

/**
 * Confidence policy over the worker's weighted Hamming distances
 * (10 × global bits + 6 × text bits). Calibrated on the browser bench with
 * the REAL detect→warp pipeline: the right card lands ≈ 550-2200 on clean
 * shots (the warp itself adds noise a pristine image never has), degraded
 * shots drift to ≈ 3000, and the first DIFFERENT card sits ≥ 1.3× away on
 * every confident case. The margin is therefore relative, not absolute; a
 * miss falls back to the server OCR pipeline — a slow correct answer beats
 * a fast wrong one.
 */
const CONFIDENT_DISTANCE_MAX = 3200
const MIN_MARGIN_TO_OTHER_CARD = 250
const MIN_RATIO_TO_OTHER_CARD = 1.12
/** Same-card entries within this window of the best hit count as language candidates. */
const SAME_CARD_LOCALE_WINDOW = 600

let indexFetchPromise: Promise<{ buffer: ArrayBuffer; cards: ScanMatchCard[] }> | null = null

/**
 * Télécharge les deux fichiers de l'index visuel (hashes binaires + méta) —
 * une seule fois par session, le cache HTTP du navigateur fait le reste.
 * @returns {Promise<{buffer: ArrayBuffer, cards: ScanMatchCard[]}>} Index binaire + métadonnées alignées.
 */
async function fetchIndexOnce(): Promise<{ buffer: ArrayBuffer; cards: ScanMatchCard[] }> {
  if (!indexFetchPromise) {
    indexFetchPromise = (async () => {
      const [binResp, jsonResp] = await Promise.all([
        fetch(`/scan-index/index-v${INDEX_VERSION}.bin`),
        fetch(`/scan-index/index-v${INDEX_VERSION}.json`),
      ])
      if (!binResp.ok || !jsonResp.ok) {
        throw new Error(`scan-index HTTP ${binResp.status}/${jsonResp.status}`)
      }
      const buffer = await binResp.arrayBuffer()
      const meta = (await jsonResp.json()) as { version: number; cards: [string, string, string, string, string][] }
      const cards: ScanMatchCard[] = meta.cards.map(([tcgdexCardId, locale, name, setId, localId]) => ({
        tcgdexCardId,
        locale,
        name,
        setId,
        localId,
      }))
      return { buffer, cards }
    })()
    indexFetchPromise.catch(() => {
      // Failed fetch must not poison later retries (flaky mobile network).
      indexFetchPromise = null
    })
  }
  return indexFetchPromise
}

/**
 * Index de reconnaissance visuelle : identification de la carte SUR le
 * téléphone (hash perceptuel matché contre toutes les images TCGdex), sans
 * OCR ni aller-retour serveur. Voir `api/scripts/build_scan_match_index.py`.
 * @returns {object} Index binaire, métadonnées, état de chargement, `load()` et `decide()`.
 */
export function useScanMatchIndex() {
  const indexBuffer: Ref<ArrayBuffer | null> = ref(null)
  const cards: Ref<ScanMatchCard[] | null> = ref(null)
  const loadFailed: Ref<boolean> = ref(false)
  const ready: ComputedRef<boolean> = computed(() => indexBuffer.value !== null && cards.value !== null)

  /**
   * Charge l'index (idempotent). En cas d'échec réseau le scanner continue
   * simplement en mode OCR serveur — jamais bloquant.
   * @returns {Promise<void>} Résolue une fois l'index chargé (ou l'échec acté).
   */
  async function load(): Promise<void> {
    if (ready.value) {
      return
    }
    try {
      const { buffer, cards: rows } = await fetchIndexOnce()
      indexBuffer.value = buffer
      cards.value = rows
      loadFailed.value = false
    } catch {
      loadFailed.value = true
    }
  }

  /**
   * Applique la politique de confiance aux candidats du worker.
   * @param matches - Paires plates `[indexEntry, distance]` triées par distance croissante.
   * @param sessionLanguage - Langue de session choisie sur l'écran scan (`auto` = déduire).
   * @returns {ScanMatchDecision | null} Identification sûre, ou `null` → pipeline OCR serveur.
   */
  function decide(matches: number[], sessionLanguage: ScanCardLanguage): ScanMatchDecision | null {
    const rows = cards.value
    if (!rows || matches.length < 2) {
      return null
    }
    const best = rows[matches[0]!]
    const bestDistance = matches[1]!
    if (!best || bestDistance > CONFIDENT_DISTANCE_MAX) {
      return null
    }
    const locales = new Set<string>([best.locale])
    for (let i = 2; i + 1 < matches.length; i += 2) {
      const row = rows[matches[i]!]
      const distance = matches[i + 1]!
      if (!row) {
        continue
      }
      if (row.tcgdexCardId === best.tcgdexCardId) {
        if (distance - bestDistance < SAME_CARD_LOCALE_WINDOW) {
          locales.add(row.locale)
        }
        continue
      }
      // First different card: the margin decides whether the hit is trustworthy.
      if (distance - bestDistance < MIN_MARGIN_TO_OTHER_CARD || distance < bestDistance * MIN_RATIO_TO_OTHER_CARD) {
        return null
      }
      break
    }
    if (locales.size > 1 && sessionLanguage === 'auto') {
      // Same card in several languages, nothing to tell them apart visually →
      // let the OCR read the actual printed text.
      return null
    }
    return {
      tcgdexCardId: best.tcgdexCardId,
      language: sessionLanguage === 'auto' ? best.locale : sessionLanguage,
      name: best.name,
      setId: best.setId,
      localId: best.localId,
    }
  }

  return { indexBuffer, cards, ready, loadFailed, load, decide }
}
