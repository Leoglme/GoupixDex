/** Catalogue statique des produits scellés Cardmarket (parcours par extension + recherche). */

export interface SealedCatalogProduct {
  /** idProduct Cardmarket. */
  p: number
  /** Nom du produit. */
  n: string
  /** Type normalisé (booster, display, etb…). */
  c: string
}

export interface SealedCatalogExpansion {
  id: number
  label: string
  count: number
  products: SealedCatalogProduct[]
}

export interface SealedCatalog {
  version: number
  generated_at: string
  expansions: SealedCatalogExpansion[]
}

let catalogPromise: Promise<SealedCatalog | null> | null = null

/**
 * Charge le catalogue statique une seule fois (mémoïsé pour la session).
 * @returns {Promise<SealedCatalog | null>} Le catalogue, ou `null` en cas d'échec.
 */
function fetchCatalogOnce(): Promise<SealedCatalog | null> {
  if (!catalogPromise) {
    catalogPromise = fetch('/sealed-catalog/sealed-v1.json')
      .then((r) => (r.ok ? (r.json() as Promise<SealedCatalog>) : null))
      .catch((): null => null)
  }
  return catalogPromise
}

/**
 * Composable du catalogue des produits scellés (chargement, recherche, cotation).
 * @returns Helpers du catalogue scellé.
 */
export function useSealedCatalog() {
  const { $api } = useNuxtApp()

  /**
   * Charge et renvoie la liste des extensions du catalogue.
   * @returns {Promise<SealedCatalogExpansion[]>} Extensions triées, ou tableau vide.
   */
  async function loadExpansions() {
    const catalog = await fetchCatalogOnce()
    return catalog?.expansions ?? []
  }

  /**
   * Recherche globale de produits par nom (toutes extensions confondues).
   * @param query - Terme de recherche (>= 2 caractères).
   * @param limit - Nombre maximum de résultats.
   * @returns {Promise<SealedCatalogProduct[]>} Produits correspondants.
   */
  async function searchProducts(query: string, limit = 60) {
    const needle = query.trim().toLowerCase()
    if (needle.length < 2) {
      return []
    }
    const catalog = await fetchCatalogOnce()
    if (!catalog) {
      return []
    }
    const hits: SealedCatalogProduct[] = []
    for (const expansion of catalog.expansions) {
      for (const product of expansion.products) {
        if (product.n.toLowerCase().includes(needle)) {
          hits.push(product)
          if (hits.length >= limit) {
            return hits
          }
        }
      }
    }
    return hits
  }

  /**
   * POST `/sealed/quote` — prix marché en lot pour des idProduct (guide local, sans quota).
   *
   * @param idProducts - Liste d'idProduct Cardmarket.
   * @returns {Promise<Record<string, number | null>>} Table idProduct vers prix EUR (ou null).
   */
  async function quotePrices(idProducts: number[]) {
    if (!idProducts.length) {
      return {}
    }
    const { data } = await $api.post<{ prices: Record<string, number | null> }>('/sealed/quote', {
      cardmarket_id_products: idProducts.slice(0, 400),
    })
    return data.prices
  }

  return { loadExpansions, searchProducts, quotePrices }
}
