import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { Marketplace } from '~/types/Marketplace'

export type ArticleMarketplacePublication = {
  publishingMarketplaces: Ref<Marketplace[]>
  publishArticleOnMarketplaces: (article: Article, marketplaces: Marketplace[]) => Promise<void>
}
