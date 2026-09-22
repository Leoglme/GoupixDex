import type { CatalogLocale } from '~/composables/useCardCatalog'
import type { SealedCatalogProduct } from '~/composables/useSealedCatalog'

/** Carte du catalogue TCGdex prévisualisée dans un drawer avant ajout à la collection. */
export type GoupixCatalogCardRef = {
  id: string
  name: string
  setName: string
  localId: string
  image: string | null
  locale: CatalogLocale
}

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

export type GoupixCatalogCardDrawerEntry = {
  kind: 'catalog-card'
  card: GoupixCatalogCardRef
}

export type GoupixDrawerStackEntry =
  | GoupixArticleDrawerEntry
  | GoupixSealedDrawerEntry
  | GoupixCardDrawerEntry
  | GoupixSealedCatalogDrawerEntry
  | GoupixCatalogCardDrawerEntry

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
