import type { Article } from '~/composables/useArticles'
import type { Marketplace } from '~/types/Marketplace'

export type GoupixDexArticleMarkSoldDrawerProps = {
  articles: Article[] | null
  isSaving: boolean
}

export type BundleSaleAllocation = {
  id: number
  soldPrice: number
}

export type ArticleSaleConfirmation =
  | { mode: 'single'; soldPrice: number; saleSource: Marketplace }
  | { mode: 'bundle'; saleSource: Marketplace; allocations: BundleSaleAllocation[] }

export type BundleSalePreviewLine = {
  id: number
  label: string
  soldPrice: number
}
