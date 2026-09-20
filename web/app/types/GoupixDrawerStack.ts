import type { SealedCatalogProduct } from '~/composables/useSealedCatalog'

export type GoupixArticleDrawerEntry = {
  kind: 'article'
  articleId: number
}

export type GoupixSealedDrawerEntry = {
  kind: 'sealed'
  sealedId: number
}

export type GoupixCardDrawerEntry = {
  kind: 'card'
  cardId: number
}

export type GoupixSealedCatalogDrawerEntry = {
  kind: 'catalog-sealed'
  product: SealedCatalogProduct
  expansionName: string
}

export type GoupixDrawerStackEntry =
  | GoupixArticleDrawerEntry
  | GoupixSealedDrawerEntry
  | GoupixCardDrawerEntry
  | GoupixSealedCatalogDrawerEntry

export type GoupixArticleMutationNotice = {
  type: 'updated'
  articleId: number
}

export type GoupixSealedMutationNotice = {
  type: 'updated' | 'deleted'
  sealedId: number
}

export type GoupixCardMutationNotice = {
  type: 'updated' | 'deleted'
  cardId: number
}
