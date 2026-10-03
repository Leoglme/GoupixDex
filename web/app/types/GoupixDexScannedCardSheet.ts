import type { ScannedCard } from '~/types/ScannedCardSheet'

export type GoupixDexScannedCardSheetProps = {
  scannedCard: ScannedCard
  isEmbedded: boolean
}

export type ScannedCardActionButton = {
  key: string
  binderId: number | null
  idleLabel: string
  pendingLabel: string
  doneLabel: string
  idleIcon: string
}
