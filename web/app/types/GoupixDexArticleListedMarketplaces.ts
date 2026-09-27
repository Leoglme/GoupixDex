import type { ArticleMarketplaceListings, Marketplace } from '~/types/Marketplace'

export type GoupixDexArticleListedMarketplacesProps = {
  row: ArticleMarketplaceListings
  showVinted?: boolean
  showEbay?: boolean
  showLeboncoin?: boolean
  hasListingLinks?: boolean
}

export type ListedMarketplaceIcon = {
  marketplace: Marketplace
  isPublished: boolean
  listingUrl: string | null
}
