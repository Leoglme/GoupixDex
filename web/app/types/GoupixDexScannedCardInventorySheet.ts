import type { Marketplace, MarketplaceSetupIssues } from '~/types/Marketplace'
import type { ScannedCard } from '~/types/ScannedCardSheet'

export type GoupixDexScannedCardInventorySheetProps = {
  scannedCard: ScannedCard
  publishingMarketplaces: Marketplace[]
  marketplaceSetupIssues: MarketplaceSetupIssues
  isOpeningListingWizard: boolean
  isEmbedded: boolean
}

export type ScannedCardSaleStepStatus = 'done' | 'todo' | 'blocked' | 'in-progress'

export type ScannedCardSaleStepMarketplace = {
  marketplace: Marketplace
  isOnline: boolean
  isPublishing: boolean
}

export type ScannedCardSaleStep = {
  name: 'collection' | 'article' | 'online'
  status: ScannedCardSaleStepStatus
  label: string
  detail: string | null
  marketplaces: ScannedCardSaleStepMarketplace[]
  canOpenArticleEditor: boolean
}

export type ScannedCardSaleAction = 'add-to-collection' | 'put-online' | 'publish'

export type ScannedCardSaleActionButton = {
  action: ScannedCardSaleAction
  label: string
  hint: string | null
  icon: string
  marketplaces: Marketplace[]
}

export type ScannedCardSaleStatusMessage = {
  text: string
  isSaleComplete: boolean
}
