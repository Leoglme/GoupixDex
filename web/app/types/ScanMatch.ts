/** One card entry of the prebuilt visual-match index (`/scan-index/index-v{N}.json`). */
export type ScanMatchCard = {
  tcgdexCardId: string
  locale: string
  name: string
  setId: string
  localId: string
}

/** Confident on-device identification, ready to commit without OCR. */
export type ScanMatchDecision = {
  tcgdexCardId: string
  /** Language stored in the collection (session selector, or the matched locale). */
  language: string
  name: string
  setId: string
  localId: string
}

/** Physical-card language of the current scan session (`auto` = resolve per card). */
export type ScanCardLanguage = 'auto' | 'ja' | 'en' | 'fr'

/** Résultat brut d'une tentative d'identification (décision + meilleur hit). */
export type ScanIdentifyResult = {
  /** Identification SÛRE (politique passée), ou `null`. */
  decision: ScanMatchDecision | null
  /** Meilleure carte brute de la tentative (même non confiante), ou `null`. */
  topCardId: string | null
  /** Similarité du meilleur hit (0 quand aucun). */
  topSim: number
  /** Marge du meilleur hit face au premier print DIFFÉRENT du top-8 (0 quand aucun hit). */
  topMargin: number
  /** Index du crop gagnant dans la tentative — désigne la zone à verrouiller/focaliser. */
  bestCropIndex: number
}
