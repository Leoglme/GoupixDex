import type { ArticleMarketplaceListings, Marketplace, MarketplaceListingLink } from '~/types/Marketplace'

export const MARKETPLACE_NAMES: Record<Marketplace, string> = {
  vinted: 'Vinted',
  ebay: 'eBay',
  leboncoin: 'Leboncoin',
}

export const MARKETPLACES: Marketplace[] = ['vinted', 'ebay', 'leboncoin']

/**
 * Adresse publique de l'annonce d'un article sur une marketplace.
 * @param {ArticleMarketplaceListings} article - Statuts de publication et identifiants d'annonce de l'article.
 * @param {Marketplace} marketplace - Marketplace visée.
 * @returns {string | null} L'URL de l'annonce, ou null si l'article n'y est pas en ligne.
 */
export function marketplaceListingUrl(article: ArticleMarketplaceListings, marketplace: Marketplace): string | null {
  if (marketplace === 'vinted') {
    return article.published_on_vinted && article.vinted_id ? `https://www.vinted.fr/items/${article.vinted_id}` : null
  }
  if (marketplace === 'ebay') {
    return article.published_on_ebay && article.ebay_listing_id
      ? `https://www.ebay.fr/itm/${article.ebay_listing_id}`
      : null
  }
  return article.published_on_leboncoin && article.leboncoin_listing_id
    ? `https://www.leboncoin.fr/ad/collection/${article.leboncoin_listing_id}`
    : null
}

/**
 * Liens vers les annonces en ligne d'un article, dans l'ordre Vinted, eBay, Leboncoin.
 * @param {ArticleMarketplaceListings} article - Statuts de publication et identifiants d'annonce de l'article.
 * @returns {MarketplaceListingLink[]} Une entrée par annonce dont l'URL est connue.
 */
export function marketplaceListingLinks(article: ArticleMarketplaceListings): MarketplaceListingLink[] {
  return MARKETPLACES.flatMap((marketplace: Marketplace): MarketplaceListingLink[] => {
    const url: string | null = marketplaceListingUrl(article, marketplace)
    return url ? [{ marketplace, url }] : []
  })
}
