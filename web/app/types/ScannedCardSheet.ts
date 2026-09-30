import type { Ref } from 'vue'
import type { ScanDirection, ScanEvent } from '~/composables/useScanStream'
import type { ScanMatchDecision } from '~/types/ScanMatch'

export type ScannedCardPreview = {
  tcgdex_card_id: string
  tcgdex_set_id: string
  language: string
  display_name: string
  set_name: string | null
  set_code: string | null
  card_number: string
  printed_set_total: number | null
  image_url: string | null
  market_price_eur: number | null
  owned_quantity: number
}

export type ScannedCardAction = 'idle' | 'pending' | 'done' | 'failed'

export type ScannedCard = {
  decision: ScanMatchDecision
  imageUrl: string
  direction: ScanDirection
  preview: ScannedCardPreview | null
  isPreviewLoading: boolean
  ownedQuantity: number | null
  action: ScannedCardAction
  actionEventId: string | null
  actionError: string | null
}

export type ScannedCardSheetDependencies = {
  events: Ref<ScanEvent[]>
  fetchScannedCardPreview: (tcgdexCardId: string, language: string) => Promise<ScannedCardPreview>
  commitMatchedScan: (
    tcgdexCardId: string,
    language: string,
    direction: ScanDirection,
    eventId: string,
  ) => Promise<unknown>
}

export type ScannedCardSheet = {
  scannedCard: Ref<ScannedCard | null>
  showScannedCard: (decision: ScanMatchDecision, imageUrl: string, direction: ScanDirection) => void
  confirmScannedCardAction: () => Promise<void>
  dismissScannedCard: () => void
}
