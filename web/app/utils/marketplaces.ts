import type { AppSettings } from '~/composables/useSettings'
import type {
  ArticleMarketplaceListings,
  ArticlePublicationDates,
  Marketplace,
  MarketplaceListingLink,
  MarketplaceSetupIssues,
} from '~/types/Marketplace'

export const MARKETPLACE_NAMES: Record<Marketplace, string> = {
  vinted: 'Vinted',
  ebay: 'eBay',
  leboncoin: 'Leboncoin',
}

export const MARKETPLACES: Marketplace[] = ['vinted', 'ebay', 'leboncoin']

export const LEBONCOIN_MY_ADS_URL: string = 'https://www.leboncoin.fr/compte/part/mes-annonces'

/**
 * Adresse de l'annonce d'un article sur une marketplace ; sur Leboncoin sans identifiant d'annonce, la page « Mes annonces ».
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
  if (!article.published_on_leboncoin) {
    return null
  }
  return article.leboncoin_listing_id
    ? `https://www.leboncoin.fr/ad/collection/${article.leboncoin_listing_id}`
    : LEBONCOIN_MY_ADS_URL
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

/**
 * Date de la dernière mise en ligne de l'article, toutes marketplaces confondues.
 * @param {ArticlePublicationDates} article - Dates de publication de l'article sur chaque marketplace.
 * @returns {string | null} La date ISO la plus récente, ou null si l'article n'est en ligne nulle part.
 */
export function latestPublicationDate(article: ArticlePublicationDates): string | null {
  let latestDate: string | null = null
  for (const publishedAt of [article.vinted_published_at, article.ebay_published_at, article.leboncoin_published_at]) {
    if (publishedAt && (latestDate === null || new Date(publishedAt).getTime() > new Date(latestDate).getTime())) {
      latestDate = publishedAt
    }
  }
  return latestDate
}

/**
 * Vrai quand l'article est marqué en ligne sur la marketplace.
 * @param {ArticleMarketplaceListings} article - Statuts de publication de l'article.
 * @param {Marketplace} marketplace - Marketplace visée.
 * @returns {boolean} Vrai si une annonce y est en ligne.
 */
export function isPublishedOnMarketplace(article: ArticleMarketplaceListings, marketplace: Marketplace): boolean {
  if (marketplace === 'vinted') {
    return article.published_on_vinted === true
  }
  if (marketplace === 'ebay') {
    return article.published_on_ebay === true
  }
  return article.published_on_leboncoin === true
}

/**
 * Réglage à faire avant de pouvoir publier sur chaque marketplace, d'après les paramètres du compte.
 * @param {AppSettings} settings - Paramètres du compte.
 * @returns {MarketplaceSetupIssues} Le réglage manquant par marketplace, ou null quand elle est prête.
 */
export function findMarketplaceSetupIssues(settings: AppSettings): MarketplaceSetupIssues {
  return {
    vinted: settings.vinted_enabled ? null : 'Activez Vinted dans les paramètres.',
    ebay: findEbaySetupIssue(settings),
    leboncoin: findLeboncoinSetupIssue(settings),
  }
}

/**
 * Premier réglage eBay manquant, dans l'ordre où il faut les faire.
 * @param {AppSettings} settings - Paramètres du compte.
 * @returns {string | null} Le réglage à faire, ou null quand eBay est prêt.
 */
function findEbaySetupIssue(settings: AppSettings): string | null {
  if (!settings.ebay_enabled) {
    return 'Activez eBay dans les paramètres.'
  }
  if (!settings.ebay_oauth_configured) {
    return 'La connexion eBay n’est pas configurée sur le serveur.'
  }
  if (!settings.ebay_connected) {
    return 'Connectez votre compte eBay dans les paramètres.'
  }
  if (!settings.ebay_listing_config_complete) {
    return 'Complétez les réglages des annonces eBay dans les paramètres.'
  }
  return null
}

/**
 * Premier réglage Leboncoin manquant : l'activation, puis l'adresse expéditeur.
 * @param {AppSettings} settings - Paramètres du compte.
 * @returns {string | null} Le réglage à faire, ou null quand Leboncoin est prêt.
 */
function findLeboncoinSetupIssue(settings: AppSettings): string | null {
  if (!settings.leboncoin_enabled) {
    return 'Activez Leboncoin dans les paramètres.'
  }
  if (!settings.sender_address_complete) {
    return 'Complétez l’adresse expéditeur dans Mon profil.'
  }
  return null
}

/**
 * Noms des marketplaces pour une phrase : « Vinted, eBay et Leboncoin ».
 * @param {Marketplace[]} marketplaces - Marketplaces à nommer.
 * @returns {string} Les noms séparés par des virgules, le dernier par « et ».
 */
export function marketplaceNamesLabel(marketplaces: Marketplace[]): string {
  return new Intl.ListFormat('fr', { style: 'long', type: 'conjunction' }).format(
    marketplaces.map((marketplace: Marketplace): string => MARKETPLACE_NAMES[marketplace]),
  )
}

/**
 * Marketplaces d'un paramètre d'URL « vinted,ebay » ; les valeurs inconnues sont ignorées.
 * @param {unknown} rawList - Valeur du paramètre.
 * @returns {Marketplace[]} Les marketplaces reconnues, dans l'ordre Vinted, eBay, Leboncoin.
 */
export function parseMarketplaceList(rawList: unknown): Marketplace[] {
  if (typeof rawList !== 'string') {
    return []
  }
  const requestedMarketplaces: string[] = rawList.split(',').map((value: string): string => value.trim())
  return MARKETPLACES.filter((marketplace: Marketplace): boolean => requestedMarketplaces.includes(marketplace))
}
