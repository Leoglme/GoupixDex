import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { Marketplace } from '~/types/Marketplace'

export type ArticleFinder = (articleId: number) => Article | undefined

export type BulkMarketplacePublication = {
  isPublishingInBulk: Ref<boolean>
  publishArticlesInBulk: (articleIds: number[], marketplaces: Marketplace[]) => Promise<void>
}
