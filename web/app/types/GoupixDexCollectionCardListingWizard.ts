import type { CollectionArticlePrefillResponse, CollectionCard } from '~/composables/useCollection'

export type CollectionCardListingStep = 'front' | 'back' | 'photos' | 'article'

export type CollectionCardListingStepOption = {
  step: CollectionCardListingStep
  label: string
}

export type ArticleCreateFormHandle = {
  applyCatalogPrefill: (prefill: CollectionArticlePrefillResponse) => Promise<void>
  addImageFiles: (files: File[]) => void
  submit: () => void
}

export type GoupixDexCollectionCardListingWizardProps = {
  open: boolean
  card: CollectionCard
}
