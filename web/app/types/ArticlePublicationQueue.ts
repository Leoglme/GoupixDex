import type { Ref } from 'vue'
import type { Marketplace } from '~/types/Marketplace'

export type ArticlePublication = {
  articleId: number
  marketplace: Marketplace
}

export type ArticlePublicationQueue = {
  pendingPublications: Ref<ArticlePublication[]>
  queueArticlePublication: (articleId: number, marketplaces: Marketplace[]) => void
  publishingMarketplacesOfArticle: (articleId: number) => Marketplace[]
}
