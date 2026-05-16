/** Personal Pokémon card collection (decoupled from sale articles). */

import type { CatalogCardPreviewResponse } from '~/composables/useCardCatalog'

export type CollectionLanguage = 'fr' | 'en' | 'ja'

export interface CollectionCard {
  id: number
  tcgdex_card_id: string
  tcgdex_set_id: string
  set_code: string | null
  set_name: string | null
  card_number: string
  card_name_en: string | null
  card_name_fr: string | null
  card_name_ja: string | null
  display_name: string
  rarity: string | null
  language: CollectionLanguage | string
  image_url: string | null
  quantity: number
  notes: string | null
  article_id: number | null
  created_at: string
  updated_at: string
}

export interface CollectionStats {
  unique_cards: number
  total_quantity: number
  unique_sets: number
  languages: Record<string, number>
  with_article: number
}

export interface CollectionListResponse {
  items: CollectionCard[]
  stats: CollectionStats
}

export interface CollectionAddBody {
  tcgdex_card_id: string
  language: CollectionLanguage | string
  quantity?: number
  notes?: string | null
}

export interface CollectionAddResponse {
  created: boolean
  card: CollectionCard
}

export interface CollectionPatchBody {
  quantity?: number
  language?: CollectionLanguage | string
  notes?: string | null
}

export interface CollectionArticlePrefillResponse extends CatalogCardPreviewResponse {
  collection_card_id: number
  physical_language: CollectionLanguage | string
}

/**
 * Composable « Ma Collection » (proxy GoupixDex authentifié).
 *
 * @returns Helpers async pour la collection personnelle Pokémon.
 */
export function useCollection() {
  const { $api } = useNuxtApp()

  /**
   * GET `/collection` — paginated binder list + aggregated stats.
   *
   * @param params - Search / language / set / listed-state filters.
   * @returns {Promise<CollectionListResponse>} Items + header stats.
   */
  async function listCollection(params?: {
    search?: string
    language?: CollectionLanguage | string
    setId?: string
    listed?: 'any' | 'with_article' | 'without_article'
  }) {
    const { data } = await $api.get<CollectionListResponse>('/collection', {
      params: {
        search: params?.search?.trim() || undefined,
        language: params?.language || undefined,
        set_id: params?.setId || undefined,
        listed: params?.listed || undefined,
      },
    })
    return data
  }

  /**
   * POST `/collection` — add a card; existing `(card_id, language)` increments quantity.
   *
   * @param body - TCGdex card id + physical language.
   * @returns {Promise<CollectionAddResponse>} `{ created, card }`.
   */
  async function addToCollection(body: CollectionAddBody) {
    const { data } = await $api.post<CollectionAddResponse>('/collection', body)
    return data
  }

  /**
   * GET `/collection/:id` — single card detail.
   *
   * @param id - Collection card id.
   * @returns {Promise<CollectionCard>} Card row.
   */
  async function getCollectionCard(id: number) {
    const { data } = await $api.get<CollectionCard>(`/collection/${id}`)
    return data
  }

  /**
   * PATCH `/collection/:id` — partial update (quantity, language, notes).
   *
   * @param id - Collection card id.
   * @param body - Partial patch fields.
   * @returns {Promise<CollectionCard>} Updated row.
   */
  async function patchCollectionCard(id: number, body: CollectionPatchBody) {
    const { data } = await $api.patch<CollectionCard>(`/collection/${id}`, body)
    return data
  }

  /**
   * DELETE `/collection/:id` — remove a card from the binder.
   *
   * @param id - Collection card id.
   * @returns {Promise<void>} Resolves on 204.
   */
  async function deleteCollectionCard(id: number) {
    await $api.delete(`/collection/${id}`)
  }

  /**
   * POST `/collection/:id/prepare-article-prefill` — payload for `ArticleForm.applyCatalogPrefill`.
   *
   * @param id - Collection card id.
   * @param refreshPricing - Hit pricing service for an updated cardmarket / suggested price.
   * @returns {Promise<CollectionArticlePrefillResponse>} Catalog-style preview payload.
   */
  async function prepareArticlePrefill(id: number, refreshPricing = true) {
    const { data } = await $api.post<CollectionArticlePrefillResponse>(`/collection/${id}/prepare-article-prefill`, {
      refresh_pricing: refreshPricing,
    })
    return data
  }

  /**
   * POST `/collection/:id/attach-article?article_id=...` — link an existing article back.
   *
   * @param id - Collection card id.
   * @param articleId - Owned article id to link.
   * @returns {Promise<CollectionCard>} Updated collection card row.
   */
  async function attachArticle(id: number, articleId: number) {
    const { data } = await $api.post<CollectionCard>(`/collection/${id}/attach-article`, undefined, {
      params: { article_id: articleId },
    })
    return data
  }

  return {
    listCollection,
    addToCollection,
    getCollectionCard,
    patchCollectionCard,
    deleteCollectionCard,
    prepareArticlePrefill,
    attachArticle,
  }
}
