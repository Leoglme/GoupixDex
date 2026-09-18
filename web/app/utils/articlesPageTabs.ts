// app/utils/articlesPageTabs.ts
import type { GoupixDexPageTabItem } from '~/types/GoupixDexPageTabs'

/**
 * Shared tab strip of the "Mes articles" section (stock / listed / sold pages).
 */
export const ARTICLES_PAGE_TABS: GoupixDexPageTabItem[] = [
  { label: 'Stock', to: '/articles/stock', icon: 'i-lucide-package' },
  { label: 'En ligne', to: '/articles', icon: 'i-lucide-store' },
  { label: 'Vendus', to: '/articles/sold', icon: 'i-lucide-badge-check' },
]
