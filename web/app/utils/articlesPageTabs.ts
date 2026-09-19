// app/utils/articlesPageTabs.ts
import type { GoupixDexPageTabItem } from '~/types/GoupixDexPageTabs'

/**
 * Shared tab strip of the "Mes articles" section (active sales / sold).
 */
export const ARTICLES_PAGE_TABS: GoupixDexPageTabItem[] = [
  { label: 'En vente', to: '/articles', icon: 'i-lucide-store' },
  { label: 'Vendus', to: '/articles/sold', icon: 'i-lucide-badge-check' },
]
