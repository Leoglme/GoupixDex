import type { Marketplace } from '~/types/Marketplace'

export type GoupixDexMarketplaceButtonAction = 'delist' | 'open'

export type GoupixDexMarketplaceButtonProps = {
  marketplace: Marketplace
  action: GoupixDexMarketplaceButtonAction
  isLoading: boolean
  isDisabled: boolean
  href: string | null
}
