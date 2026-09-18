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
