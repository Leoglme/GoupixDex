import type { Article } from '~/composables/useArticles'

export type SoldArticleListingsRemover = {
  removeListingsLeftOnline: (soldArticles: Article[]) => void
}
