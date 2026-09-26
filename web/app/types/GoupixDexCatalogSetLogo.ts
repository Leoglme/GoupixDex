import type { CatalogLocale } from '~/composables/useCardCatalog'

export type GoupixDexCatalogSetLogoProps = {
  logo?: string
  symbol?: string
  cover?: string
  fallbackImages?: string[]
  name: string
  large?: boolean
  setId?: string
  locale?: CatalogLocale
}
