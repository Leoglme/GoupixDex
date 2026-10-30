import type { ScannedCard } from '~/types/ScannedCardSheet'

export type GoupixDexScannedCardSheetProps = {
  scannedCard: ScannedCard
  isEmbedded: boolean
}

export type ScannedCardActionButton = {
  idleLabel: string
  pendingLabel: string
  doneLabel: string
  idleIcon: string
}
