import type { Article } from '~/composables/useArticles'

export type SoldArticleListingsRemover = {
  removeListingsLeftOnline: (soldArticles: Article[]) => void
  fetchArticlesWithListingsLeftOnline: () => Promise<Article[]>
  removeEveryListingLeftOnline: (articlesWithListingsLeftOnline: Article[]) => Promise<void>
  startMissedListingRemovalsCatchUp: () => void
  stopMissedListingRemovalsCatchUp: () => void
}
