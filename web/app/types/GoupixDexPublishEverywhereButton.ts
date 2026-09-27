import type { DropdownMenuItem } from '@nuxt/ui'
import type { Marketplace } from '~/types/Marketplace'

export type MarketplacePublishOption = {
  marketplace: Marketplace
  blockedReason: string | null
  isPublishing: boolean
}

export type GoupixDexPublishEverywhereButtonProps = {
  publishOptions: MarketplacePublishOption[]
}

export type MarketplacePublishMenuItem = DropdownMenuItem & {
  marketplace: Marketplace
}
