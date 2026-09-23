// Lien Cardmarket vers une carte ou un produit scellé.
// Fiche produit directe via l'idProduct quand on l'a ; sinon recherche par nom + numéro.

const CARDMARKET_BASE = 'https://www.cardmarket.com/fr/Pokemon/Products'

/**
 * Fiche produit Cardmarket via l'idProduct (`?idProduct=` redirige vers la carte).
 * @param idProduct Identifiant produit Cardmarket.
 * @returns L'URL de la fiche, ou null si l'idProduct est absent.
 */
export function cardmarketProductUrl(idProduct: number | null | undefined): string | null {
  return idProduct != null && Number.isFinite(idProduct) ? `${CARDMARKET_BASE}?idProduct=${idProduct}` : null
}

/**
 * Recherche Cardmarket « nom numéro » (repli quand l'idProduct est inconnu).
 * @param name Nom de la carte / du produit.
 * @param localId Numéro de carte optionnel.
 * @returns L'URL de recherche Cardmarket.
 */
export function cardmarketSearchUrl(name: string, localId?: string | null): string {
  const query = [name, localId].filter(Boolean).join(' ')
  return `${CARDMARKET_BASE}/Search?searchString=${encodeURIComponent(query)}`
}

/**
 * Lien Cardmarket vers LA carte / LE produit : fiche produit si l'idProduct est connu, sinon recherche.
 * @param opts Identifiant produit, nom et numéro éventuels.
 * @returns L'URL Cardmarket la plus précise disponible.
 */
export function cardmarketUrl(opts: { idProduct?: number | null; name: string; localId?: string | null }): string {
  return cardmarketProductUrl(opts.idProduct) ?? cardmarketSearchUrl(opts.name, opts.localId)
}
