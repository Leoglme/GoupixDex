/** Catalogue statique des produits scellés (série vers extension vers produits, images réelles). */

export interface SealedCatalogProduct {
  /** idProduct TCGplayer (image + identité catalogue). */
  tp: number
  /** idProduct Cardmarket (prix € + revalorisation nocturne) — ``null`` si non apparié. */
  p: number | null
  /** Nom court (sans le nom de l'extension). */
  n: string
  /** Nom complet d'origine. */
  full: string
  /** Type normalisé (etb, display, tin…). */
  c: string
  /** URL de l'image réelle (TCGplayer CDN) — ``null`` si absente. */
  img: string | null
  /** Prix de référence en € — ``null`` si inconnu. */
  price: number | null
}

export interface SealedCatalogExpansion {
  id: string
  name: string
  logo: string | null
  count: number
  products: SealedCatalogProduct[]
}

export interface SealedCatalogSerie {
  name: string
  logo: string | null
  expansions: SealedCatalogExpansion[]
}

export interface SealedCatalog {
  version: number
  generated_at: string
  series: SealedCatalogSerie[]
}

export interface SealedCatalogSearchHit {
  product: SealedCatalogProduct
  expansionName: string
}

let catalogPromise: Promise<SealedCatalog | null> | null = null

/**
 * Charge le catalogue statique une seule fois (mémoïsé pour la session).
 * @returns {Promise<SealedCatalog | null>} Le catalogue, ou `null` en cas d'échec.
 */
function fetchCatalogOnce(): Promise<SealedCatalog | null> {
  if (!catalogPromise) {
    catalogPromise = fetch('/sealed-catalog/sealed-v2.json')
      .then((r) => (r.ok ? (r.json() as Promise<SealedCatalog>) : null))
      .catch((): null => null)
  }
  return catalogPromise
}

/**
 * Composable du catalogue des produits scellés (chargement, recherche globale).
 * @returns Helpers du catalogue scellé.
 */
export function useSealedCatalog() {
  /**
   * Charge et renvoie les séries du catalogue (chaque série contient ses extensions).
   * @returns {Promise<SealedCatalogSerie[]>} Séries, ou tableau vide.
   */
  async function loadSeries() {
    const catalog = await fetchCatalogOnce()
    return catalog?.series ?? []
  }

  /**
   * Recherche globale de produits par nom (toutes extensions confondues).
   * @param query - Terme de recherche (>= 2 caractères).
   * @param limit - Nombre maximum de résultats.
   * @returns {Promise<SealedCatalogSearchHit[]>} Produits correspondants + leur extension.
   */
  async function searchProducts(query: string, limit = 80) {
    const needle = query.trim().toLowerCase()
    if (needle.length < 2) {
      return []
    }
    const catalog = await fetchCatalogOnce()
    if (!catalog) {
      return []
    }
    const hits: SealedCatalogSearchHit[] = []
    for (const serie of catalog.series) {
      for (const expansion of serie.expansions) {
        for (const product of expansion.products) {
          if (product.full.toLowerCase().includes(needle)) {
            hits.push({ product, expansionName: expansion.name })
            if (hits.length >= limit) {
              return hits
            }
          }
        }
      }
    }
    return hits
  }

  return { loadSeries, searchProducts }
}
