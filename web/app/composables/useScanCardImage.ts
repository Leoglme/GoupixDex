import type { ScanMatchDecision } from '~/types/ScanMatch'
import { scanPhashDeltaUrl } from '~/utils/cards/scanPhashDelta'

type ScanPhashDeltaRow = [
  tcgdexCardId: string,
  locale: string,
  name: string,
  setId: string,
  localId: string,
  hashesBase64: string,
  imageUrl: string,
]

/**
 * Images STOCKÉES (id TCGdex vers URL) : les JA récentes dont TCGdex n'a pas
 * l'image (CDN limitless), livrées à part (~900 Ko). Chargées une fois.
 */
let storedImages: Record<string, string> = {}
let deltaImageByLocaleAndCardId: Record<string, string> = {}
let imagesPromise: Promise<void> | null = null

/**
 * Lit la table d'images livrée avec l'index.
 * @returns {Promise<Record<string, string>>} Id TCGdex vers URL, vide en cas d'échec.
 */
async function fetchShippedImages(): Promise<Record<string, string>> {
  try {
    const response: Response = await fetch('/scan-index/phash-images.json')
    return response.ok ? ((await response.json()) as Record<string, string>) : {}
  } catch {
    return {}
  }
}

/**
 * Lit les images des cartes calculées par l'API (même réponse que celle chargée par le worker pHash).
 * @param {string} deltaUrl - URL de `GET /scan-index/phash-delta`.
 * @returns {Promise<Record<string, string>>} `langue/id` vers URL, vide en cas d'échec.
 */
async function fetchDeltaImages(deltaUrl: string): Promise<Record<string, string>> {
  try {
    const response: Response = await fetch(deltaUrl)
    if (!response.ok) {
      return {}
    }
    const body: { cards?: ScanPhashDeltaRow[] } = await response.json()
    const images: Record<string, string> = {}
    for (const [tcgdexCardId, locale, , , , , imageUrl] of body.cards ?? []) {
      if (imageUrl) {
        images[`${locale}/${tcgdexCardId}`] = imageUrl
      }
    }
    return images
  } catch {
    return {}
  }
}

/**
 * Charge les tables d'images stockées (idempotent, non bloquant). Un échec
 * laisse la construction depuis l'id TCGdex prendre le relais.
 * @param {string} deltaUrl - URL de `GET /scan-index/phash-delta`.
 * @returns {Promise<void>} Résolue quand les tables sont chargées (ou l'échec acté).
 */
function loadStoredImages(deltaUrl: string): Promise<void> {
  if (!imagesPromise) {
    imagesPromise = Promise.all([fetchShippedImages(), fetchDeltaImages(deltaUrl)]).then(
      ([shipped, delta]: [Record<string, string>, Record<string, string>]): void => {
        storedImages = shipped
        deltaImageByLocaleAndCardId = delta
      },
    )
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
  const stored =
    deltaImageByLocaleAndCardId[`${decision.language}/${decision.tcgdexCardId}`] ?? storedImages[decision.tcgdexCardId]
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
  const deltaUrl: string = scanPhashDeltaUrl()
  return { loadStoredImages: (): Promise<void> => loadStoredImages(deltaUrl), cardImageUrl }
}
