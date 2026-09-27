import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'

export type EbayLeboncoinChannels = {
  ebay: boolean
  leboncoin: boolean
}

export type EbayLeboncoinDelistFailure = {
  articleId: number
  articleTitle: string
  reason: string
}

export type EbayLeboncoinDelist = {
  vintedDelistJobId: string | null
  isRunning: boolean
  processedCount: number
  totalCount: number
  removedFromEbayCount: number
  removedFromLeboncoinCount: number
  failures: EbayLeboncoinDelistFailure[]
}

export type EbayLeboncoinDelistTracker = {
  ebayLeboncoinDelist: Ref<EbayLeboncoinDelist | null>
  removeEbayLeboncoinListings: (
    articles: Article[],
    channels: EbayLeboncoinChannels,
    vintedDelistJobId: string | null,
  ) => Promise<EbayLeboncoinDelist>
}
