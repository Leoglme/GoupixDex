import type { ScanMatchDecision } from '~/types/ScanMatch'

/**
 * Images STOCKÉES (id TCGdex vers URL) : les JA récentes dont TCGdex n'a pas
 * l'image (CDN limitless), livrées à part (~900 Ko). Chargées une fois.
 */
let storedImages: Record<string, string> = {}
let imagesPromise: Promise<void> | null = null

/**
 * Charge la table des images stockées (idempotent, non bloquant). Un échec
 * laisse la construction depuis l'id TCGdex prendre le relais.
 * @returns {Promise<void>} Résolue quand la table est chargée (ou l'échec acté).
 */
function loadStoredImages(): Promise<void> {
  if (!imagesPromise) {
    imagesPromise = fetch('/scan-index/phash-images.json')
      .then((r) => (r.ok ? r.json() : {}))
      .then((m: Record<string, string>) => {
        storedImages = m
      })
      .catch((): void => {
        storedImages = {}
      })
  }
  return imagesPromise
}

/**
 * Série TCGdex déduite d'un id de set : les lettres de tête (me02 vers me,
 * sv03 vers sv, swsh2 vers swsh) — suffit à construire l'URL d'image.
 * @param setId - Identifiant de set TCGdex.
 * @returns {string} La série.
 */
function deriveSerie(setId: string): string {
  const m = setId.match(/^[A-Za-z]+/)
  return m ? m[0] : setId
}

/**
 * URL d'image d'une carte reconnue, disponible IMMÉDIATEMENT (sans attendre
 * l'API) : image stockée si TCGdex ne l'a pas, sinon construite depuis l'id.
 * @param decision - Carte reconnue.
 * @returns {string} URL de la vignette.
 */
function cardImageUrl(decision: ScanMatchDecision): string {
  const stored = storedImages[decision.tcgdexCardId]
  if (stored) {
    return stored
  }
  const serie = deriveSerie(decision.setId)
  return `https://assets.tcgdex.net/${decision.language}/${serie}/${decision.setId}/${decision.localId}/low.webp`
}

/**
 * Fournit l'URL d'image d'une carte reconnue AVANT le retour de l'API, pour un
 * affichage instantané de la vignette dans la fiche (voir `scan.vue`).
 * @returns {object} `loadStoredImages()` et `cardImageUrl()`.
 */
export function useScanCardImage() {
  return { loadStoredImages, cardImageUrl }
}
