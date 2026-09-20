import type { Article } from '~/composables/useArticles'

/** Annonce encore active sur au moins une marketplace suivie par GoupixDex. */
export function articleLiveOnMarketplace(
  a: Pick<Article, 'published_on_vinted' | 'published_on_ebay' | 'published_on_leboncoin'>,
): boolean {
  return Boolean(a.published_on_vinted || a.published_on_ebay || a.published_on_leboncoin)
}

/**
 * Fiche masquée dans « Mes articles » après un retrait total sur toutes les marketplaces.
 */
export function articleWithdrawnFromSale(a: Pick<Article, 'is_sold' | 'offers_for_sale'>): boolean {
  return !a.is_sold && a.offers_for_sale === false
}

/** Annonce Vinted encore active — « relister » = retirer puis republier pour remonter dans le fil. */
export function articleEligibleForVintedRelist(
  a: Pick<Article, 'is_sold' | 'offers_for_sale' | 'published_on_vinted'>,
): boolean {
  return !a.is_sold && Boolean(a.published_on_vinted) && (a.offers_for_sale ?? true)
}

export function articleEligibleForBulkRelist(
  a: Pick<Article, 'is_sold' | 'offers_for_sale' | 'published_on_vinted'>,
): boolean {
  return articleWithdrawnFromSale(a) || articleEligibleForVintedRelist(a)
}

export type BulkRelistModalMode = 'vinted-renew' | 'restore-sale'
