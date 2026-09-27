import type { Marketplace } from '~/types/Marketplace'

export type GoupixDexMarketplaceButtonAction = 'publish' | 'delist' | 'open'

export type GoupixDexMarketplaceButtonProps = {
  marketplace: Marketplace
  action: GoupixDexMarketplaceButtonAction
  isLoading: boolean
  isDisabled: boolean
  disabledReason: string | null
  href: string | null
}
