// app/utils/marketPageTabs.ts
import type { GoupixDexPageTabItem } from '~/types/GoupixDexPageTabs'

/**
 * Shared tab strip of the "Marché eBay" section (active listings / completed sales pages).
 */
export const MARKET_PAGE_TABS: GoupixDexPageTabItem[] = [
  { label: 'Annonces en cours', to: '/market', icon: 'i-lucide-tag' },
  { label: 'Ventes terminées', to: '/top-ventes-ebay', icon: 'i-lucide-history' },
]
