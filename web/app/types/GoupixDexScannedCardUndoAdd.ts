import type { ScannedCardAdd } from '~/types/ScannedCardSheet'

export type GoupixDexScannedCardUndoAddProps = {
  addsFromSheet: ScannedCardAdd[]
  isUndoingLastAdd: boolean
  isDisabled: boolean
}
