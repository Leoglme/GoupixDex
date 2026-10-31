import type { ScanMatchDecision } from '~/types/ScanMatch'
import type { ScannedCard, ScannedCardPreview } from '~/types/ScannedCardSheet'
import { hasJapanese, readableCardLabel, readableSetLabel } from '~/utils/cards/readableSet'

/**
 * Nom de la carte reconnue : celui de sa fiche, sinon celui du scan, vide tant qu'un nom japonais attend sa fiche.
 * @param {ScannedCard} scannedCard - Carte reconnue par le scanner.
 * @returns {string} Le nom à afficher, ou une chaîne vide pendant le chargement de la fiche.
 */
export function scannedCardName(scannedCard: ScannedCard): string {
  const previewName: string | undefined = scannedCard.preview?.display_name
  if (previewName) {
    return previewName
  }
  const decision: ScanMatchDecision = scannedCard.decision
  return hasJapanese(decision.name) && scannedCard.isPreviewLoading
    ? ''
    : readableCardLabel(decision.name, decision.localId)
}

/**
 * Numéro imprimé de la carte reconnue : `107/094`, ou `#112` quand le total du set n'est pas imprimé.
 * @param {ScannedCard} scannedCard - Carte reconnue par le scanner.
 * @returns {string} Le numéro à afficher.
 */
export function scannedCardPrintedNumber(scannedCard: ScannedCard): string {
  const cardNumber: string = scannedCard.preview?.card_number ?? scannedCard.decision.localId
  const printedSetTotal: number | null = scannedCard.preview?.printed_set_total ?? null
  if (!/^\d+$/.test(cardNumber)) {
    return `#${cardNumber}`
  }
  if (!printedSetTotal) {
    return `#${cardNumber.padStart(3, '0')}`
  }
  const digitCount: number = Math.max(3, String(printedSetTotal).length)
  return `${cardNumber.padStart(digitCount, '0')}/${String(printedSetTotal).padStart(digitCount, '0')}`
}

/**
 * Nom du set de la carte reconnue, en lettres latines, une fois sa fiche chargée.
 * @param {ScannedCard} scannedCard - Carte reconnue par le scanner.
 * @returns {string} Le nom du set, ou une chaîne vide tant que la fiche n'est pas chargée.
 */
export function scannedCardSetName(scannedCard: ScannedCard): string {
  const preview: ScannedCardPreview | null = scannedCard.preview
  return preview ? readableSetLabel(preview.set_name, preview.set_code, preview.tcgdex_set_id) : ''
}
