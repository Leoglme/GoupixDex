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

/** Résultat du matcher pHash (empreinte artwork) : décision SÛRE ou refus. */
export type ScanPhashResult = {
  /** `match` = carte confiante (plancher + marge vs autre artwork) ; `none` = refus. */
  status: 'match' | 'none'
  /** Carte reconnue prête à committer, ou `null` si refus. */
  decision: ScanMatchDecision | null
  /** Distance de Hamming normalisée du meilleur alignement (0 = identique). */
  score: number
}

/** Résultat brut d'une tentative d'identification (décision + meilleur hit). */
export type ScanIdentifyResult = {
  /** Identification SÛRE (politique passée : plancher + marge), ou `null`. */
  decision: ScanMatchDecision | null
  /**
   * Meilleur pari résolu de la tentative — committable même sans marge (top-1
   * S0, ou print occidental v2 pour un cluster JA) — agrégé dans le temps.
   */
  topCandidate: ScanMatchDecision | null
  /** Similarité du `topCandidate` (0 quand aucun). */
  topCandidateSim: number
  /** Meilleure carte brute de la tentative (même non confiante), ou `null`. */
  topCardId: string | null
  /** Similarité du meilleur hit (0 quand aucun). */
  topSim: number
  /** Marge du meilleur hit face au premier print DIFFÉRENT du top-8 (0 quand aucun hit). */
  topMargin: number
  /** Index du crop gagnant dans la tentative — désigne la zone à verrouiller/focaliser. */
  bestCropIndex: number
}
