import type { Article } from '~/composables/useArticles'

export type Marketplace = 'vinted' | 'ebay' | 'leboncoin'

export type ArticleMarketplaceListings = Pick<
  Article,
  | 'published_on_vinted'
  | 'vinted_id'
  | 'published_on_ebay'
  | 'ebay_listing_id'
  | 'published_on_leboncoin'
  | 'leboncoin_listing_id'
>

export type MarketplaceListingLink = {
  marketplace: Marketplace
  url: string
}

export type MarketplaceSetupIssues = Record<Marketplace, string | null>
