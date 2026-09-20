/** Produits scellés de la collection (ETB, coffrets, displays…), séparés des cartes. */

import type { CatalogCardPreviewResponse } from '~/composables/useCardCatalog'

export type SealedProductType =
  | 'booster'
  | 'display'
  | 'theme_deck'
  | 'trainer_kit'
  | 'tin'
  | 'box_set'
  | 'etb'
  | 'blister'
  | 'autre'

export interface SealedProduct {
  id: number
  name: string
  product_type: SealedProductType | string
  set_name: string | null
  language: string
  image_url: string | null
  quantity: number
  purchase_price_eur: number | null
  notes: string | null
  article_id: number | null
  cardmarket_id_product: number | null
  cardmarket_url: string | null
  market_price_eur: number | null
  market_price_updated_at: string | null
  line_market_eur: number | null
  line_purchase_eur: number | null
  gain_eur: number | null
  gain_percent: number | null
  created_at: string
  updated_at: string
}

export interface SealedStats {
  unique_products: number
  total_quantity: number
  estimated_market_eur: number
  purchase_value_eur: number
  gain_eur: number
  gain_percent: number | null
  priced_products: number
  with_article: number
  by_type: Record<string, number>
}

export interface SealedListResponse {
  items: SealedProduct[]
  stats: SealedStats
}

export interface SealedCreateBody {
  name: string
  product_type: SealedProductType
  set_name?: string | null
  language?: string
  quantity?: number
  purchase_price_eur?: number | null
  notes?: string | null
  image_url?: string | null
  cardmarket_id_product?: number | null
  cardmarket_url?: string | null
  market_price_eur?: number | null
}

export interface SealedPatchBody {
  name?: string
  product_type?: SealedProductType
  set_name?: string | null
  language?: string
  quantity?: number
  purchase_price_eur?: number | null
  notes?: string | null
  image_url?: string | null
  cardmarket_id_product?: number | null
  cardmarket_url?: string | null
  market_price_eur?: number | null
}

export interface SealedCreateResponse {
  created: boolean
  product: SealedProduct
}

export interface CardmarketResolveResponse {
  id_product: number | null
  name: string | null
  image_url: string | null
  market_price_eur: number | null
  error: string | null
}

export interface SealedArticlePrefillResponse extends CatalogCardPreviewResponse {
  sealed_product_id: number
  physical_language: string
}

export interface SealedCatalogAddBody {
  cardmarket_id_product: number
  name: string
  product_type: SealedProductType
  set_name?: string | null
  language?: string
  quantity?: number
}

export interface SealedPriceHistoryPoint {
  date: string
  price_eur: number
}

export interface SealedPriceHistoryResponse {
  points: SealedPriceHistoryPoint[]
  approximate: boolean
}

/**
 * Composable « Produits scellés » (proxy GoupixDex authentifié).
 *
 * @returns Helpers async pour les produits scellés de la collection.
 */
export function useSealed() {
  const { $api } = useNuxtApp()

  /**
   * GET `/sealed` — liste des produits scellés + stats d'en-tête.
   *
   * @param params - Filtres recherche / langue / type / statut de mise en vente.
   * @returns {Promise<SealedListResponse>} Items + stats.
   */
  async function listSealed(params?: {
    search?: string
    language?: string
    productType?: string
    listed?: 'any' | 'with_article' | 'without_article'
  }) {
    const { data } = await $api.get<SealedListResponse>('/sealed', {
      params: {
        search: params?.search?.trim() || undefined,
        language: params?.language || undefined,
        product_type: params?.productType || undefined,
        listed: params?.listed || undefined,
      },
    })
    return data
  }

  /**
   * POST `/sealed` — ajoute un produit scellé.
   *
   * @param body - Champs du produit (nom, type, prix d'achat, idProduct…).
   * @returns {Promise<SealedCreateResponse>} `{ created, product }`.
   */
  async function createSealed(body: SealedCreateBody) {
    const { data } = await $api.post<SealedCreateResponse>('/sealed', body)
    return data
  }

  /**
   * POST `/sealed/resolve-cardmarket` — pré-remplit depuis une fiche Cardmarket.
   *
   * @param url - URL de la fiche produit Cardmarket.
   * @returns {Promise<CardmarketResolveResponse>} idProduct + nom + image + prix (best-effort).
   */
  async function resolveCardmarket(url: string) {
    const { data } = await $api.post<CardmarketResolveResponse>('/sealed/resolve-cardmarket', { url })
    return data
  }

  /**
   * POST `/sealed/catalog-add` — ajoute un produit choisi dans le catalogue (idempotent).
   *
   * @param body - Produit catalogue (idProduct, nom, type, langue, quantité).
   * @returns {Promise<SealedCreateResponse>} `{ created, product }`.
   */
  async function catalogAdd(body: SealedCatalogAddBody) {
    const { data } = await $api.post<SealedCreateResponse>('/sealed/catalog-add', body)
    return data
  }

  /**
   * GET `/sealed/:id` — détail d'un produit scellé.
   *
   * @param id - Identifiant du produit scellé.
   * @returns {Promise<SealedProduct>} Ligne produit.
   */
  async function getSealed(id: number) {
    const { data } = await $api.get<SealedProduct>(`/sealed/${id}`)
    return data
  }

  /**
   * GET `/sealed/:id/price-history` — courbe d'évolution du prix marché.
   *
   * @param id - Identifiant du produit scellé.
   * @returns {Promise<SealedPriceHistoryResponse>} Points datés + drapeau approximatif.
   */
  async function getPriceHistory(id: number) {
    const { data } = await $api.get<SealedPriceHistoryResponse>(`/sealed/${id}/price-history`)
    return data
  }

  /**
   * PATCH `/sealed/:id` — mise à jour partielle (seuls les champs fournis).
   *
   * @param id - Identifiant du produit scellé.
   * @param body - Champs à modifier.
   * @returns {Promise<SealedProduct>} Ligne mise à jour.
   */
  async function patchSealed(id: number, body: SealedPatchBody) {
    const { data } = await $api.patch<SealedProduct>(`/sealed/${id}`, body)
    return data
  }

  /**
   * DELETE `/sealed/:id` — supprime un produit scellé.
   *
   * @param id - Identifiant du produit scellé.
   * @returns {Promise<void>} Résolue sur 204.
   */
  async function deleteSealed(id: number) {
    await $api.delete(`/sealed/${id}`)
  }

  /**
   * POST `/sealed/:id/prepare-article-prefill` — payload pour `ArticleForm.applyCatalogPrefill`.
   *
   * @param id - Identifiant du produit scellé.
   * @param refreshPricing - Rafraîchit le prix suggéré via le service de pricing.
   * @returns {Promise<SealedArticlePrefillResponse>} Payload de prefill façon catalogue.
   */
  async function prepareArticlePrefill(id: number, refreshPricing = true) {
    const { data } = await $api.post<SealedArticlePrefillResponse>(`/sealed/${id}/prepare-article-prefill`, {
      refresh_pricing: refreshPricing,
    })
    return data
  }

  /**
   * POST `/sealed/:id/attach-article?article_id=...` — relie un article existant.
   *
   * @param id - Identifiant du produit scellé.
   * @param articleId - Identifiant de l'article possédé à relier.
   * @returns {Promise<SealedProduct>} Ligne produit mise à jour.
   */
  async function attachArticle(id: number, articleId: number) {
    const { data } = await $api.post<SealedProduct>(`/sealed/${id}/attach-article`, undefined, {
      params: { article_id: articleId },
    })
    return data
  }

  return {
    listSealed,
    createSealed,
    catalogAdd,
    resolveCardmarket,
    getSealed,
    getPriceHistory,
    patchSealed,
    deleteSealed,
    prepareArticlePrefill,
    attachArticle,
  }
}
