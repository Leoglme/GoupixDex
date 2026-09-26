/** TCGdex-backed catalog API (authenticated proxy through GoupixDex). */

import type { GoupixPriceHistoryResponse } from '~/types/PriceHistory'

export type CatalogLocale = 'en' | 'fr' | 'ja'

export interface TcgdexSetBrief {
  id: string
  name: string
  /** Latin-script label (FR/EN). Always present, replaces JA when needed. */
  display_name?: string
  logo?: string
  symbol?: string
  /** First-card preview when TCGdex omits a set logo (common for JA). */
  cover?: string
  cardCount?: { total?: number; official?: number }
}

/** Row from ``GET /catalog/series`` (TCGdex ``/series``). */
export interface TcgdexSeriesBrief {
  id: string
  name: string
  /** Latin-script label (FR/EN). Always present, replaces JA when needed. */
  display_name?: string
  logo?: string
}

/** Full series with nested extensions from ``GET /catalog/series/:id``. */
export interface TcgdexSeriesDetail extends TcgdexSeriesBrief {
  releaseDate?: string
  sets?: TcgdexSetBrief[]
}

export interface CatalogSeriesListResponse {
  locale: string
  series: TcgdexSeriesBrief[]
}

export interface CatalogSeriesDetailResponse {
  locale: string
  series: TcgdexSeriesDetail
}

export interface TcgdexSeriesWithSets extends TcgdexSeriesDetail {
  sets: TcgdexSetBrief[]
}

export interface CatalogBrowseResponse {
  locale: string
  series: TcgdexSeriesWithSets[]
  version?: number
  generated_at?: string
}

/** ``web/public/catalog-index/manifest.json`` */
export interface CatalogBrowseManifest {
  version: number
  generated_at: string
  locales: Record<CatalogLocale, string>
}

export interface CatalogSearchCardHit {
  id: string
  localId: string
  name: string
  display_name?: string
  image?: string
  image_low?: string
  set_id: string
  set_name: string
}

export interface CatalogSearchResponse {
  locale: string
  query: string
  cards: CatalogSearchCardHit[]
}

export interface TcgdexCardInSetBrief {
  id: string
  localId: string
  name: string
  /** Latin-script label (FR/EN) — used when ``name`` is in Japanese script. */
  display_name?: string
  image?: string
  /** Ready-to-use thumbnail URL (``…/low.webp``), set by GoupixDex ``GET /catalog/sets/:id``. */
  image_low?: string
  display_local_id?: string
  merged_from?: string
}

export interface TcgdexSetDetail extends TcgdexSetBrief {
  cards?: TcgdexCardInSetBrief[]
  releaseDate?: string
  serie?: { id?: string; name?: string }
  abbreviation?: { official?: string }
  tcgOnline?: string
}

export interface CatalogSetsResponse {
  locale: string
  page: number
  per_page: number
  sets: TcgdexSetBrief[]
}

export interface CatalogSetResponse {
  locale: string
  set: TcgdexSetDetail
}

export interface CatalogCardPreviewResponse {
  tcgdx_card_id: string
  /** Pokémon name to show in the form (matches ``browse_locale`` when set). */
  display_pokemon_name?: string
  tcgdex: {
    names: { en: string; fr: string; ja: string | null }
    set_id: string
    local_id: string
  }
  pokewallet: { set_code: string; card_number: string }
  listing_preview: { title: string; description: string; suggested_price: number | null }
  pricing: {
    cardmarket_eur: number | null
    tcgplayer_usd: number | null
    average_price_eur: number | null
    cardmarket_id_product?: number | null
    error: string | null
  }
  /** Amorce J-30 / J-7 / J-1 / J du guide Cardmarket, ou courbe réelle quand la carte est déjà possédée. */
  price_history?: GoupixPriceHistoryResponse
  image_url_high: string | null
  margin_percent_used: number
  /** Exemplaires déjà dans « Ma collection » (langue du catalogue, cartes en vente comprises). */
  owned_quantity?: number
  error?: string | null
}

/**
 * Composable catalogue TCGdex (proxy GoupixDex authentifié).
 *
 * @returns Helpers async pour séries, sets et prévisualisation carte.
 */
export function useCardCatalog() {
  const { $api } = useNuxtApp()

  let browseManifestPromise: Promise<CatalogBrowseManifest> | null = null

  /**
   * @returns Cached manifest pointing at per-locale browse JSON files.
   */
  function loadBrowseManifest(): Promise<CatalogBrowseManifest> {
    if (!browseManifestPromise) {
      browseManifestPromise = $fetch<CatalogBrowseManifest>('/catalog-index/manifest.json')
    }
    return browseManifestPromise
  }

  /**
   * Static browse tree (``web/public/catalog-index/``) — instant load, refreshed daily by CI.
   */
  async function browseCatalog(locale: CatalogLocale) {
    const manifest = await loadBrowseManifest()
    const file = manifest.locales[locale]
    if (!file) {
      throw new Error(`Catalogue browse index missing locale ${locale}`)
    }
    return await $fetch<CatalogBrowseResponse>(`/catalog-index/${file}`)
  }

  /** Authenticated API browse tree, fresher than the static index built on GitHub runners. */
  async function browseCatalogFromApi(locale: CatalogLocale) {
    const { data } = await $api.get<CatalogBrowseResponse>('/catalog/browse', {
      params: { locale },
    })
    return data
  }

  /**
   * GET `/catalog/search` — recherche carte par nom / numéro.
   */
  async function searchCatalogCards(locale: CatalogLocale, q: string) {
    const { data } = await $api.get<CatalogSearchResponse>('/catalog/search', {
      params: { locale, q: q.trim() },
    })
    return data
  }

  /**
   *
   */
  async function listSeries(params: { locale: CatalogLocale; name?: string }) {
    const { data } = await $api.get<CatalogSeriesListResponse>('/catalog/series', {
      params: {
        locale: params.locale,
        name: params.name?.trim() || undefined,
      },
    })
    return data
  }

  /**
   * GET `/catalog/series/:id` — détail d’une série et ses extensions.
   *
   * @param locale - Langue catalogue.
   * @param seriesId - Identifiant série TCGdex.
   * @returns {Promise<CatalogSeriesDetailResponse>} Série avec sets imbriqués.
   */
  async function getSeries(locale: CatalogLocale, seriesId: string) {
    const { data } = await $api.get<CatalogSeriesDetailResponse>(`/catalog/series/${encodeURIComponent(seriesId)}`, {
      params: { locale },
    })
    return data
  }

  /**
   * GET `/catalog/sets` — liste paginée des extensions.
   *
   * @param params - Locale, pagination et filtre nom optionnel.
   * @returns {Promise<CatalogSetsResponse>} Page de sets.
   */
  async function listSets(params: { locale: CatalogLocale; page?: number; perPage?: number; name?: string }) {
    const { data } = await $api.get<CatalogSetsResponse>('/catalog/sets', {
      params: {
        locale: params.locale,
        page: params.page ?? 1,
        per_page: params.perPage ?? 50,
        name: params.name?.trim() || undefined,
      },
    })
    return data
  }

  /**
   * GET `/catalog/sets/:id` — détail d’une extension et ses cartes.
   *
   * @param locale - Langue catalogue.
   * @param setId - Identifiant set TCGdex.
   * @returns {Promise<CatalogSetResponse>} Set avec cartes.
   */
  async function getSet(locale: CatalogLocale, setId: string) {
    const { data } = await $api.get<CatalogSetResponse>(`/catalog/sets/${encodeURIComponent(setId)}`, {
      params: { locale },
    })
    return data
  }

  /**
   * GET `/catalog/card-preview` — titre, description, prix et image pour préremplir un article.
   *
   * @param tcgdxCardId - Identifiant carte TCGdex.
   * @param pokewalletSetCode - Code set PokéWallet optionnel.
   * @param browseLocale - Locale navigation pour le nom affiché.
   * @returns {Promise<CatalogCardPreviewResponse>} Données de prévisualisation listing.
   */
  async function previewCard(
    tcgdxCardId: string,
    pokewalletSetCode?: string | null,
    browseLocale?: CatalogLocale | null,
  ) {
    const { data } = await $api.get<CatalogCardPreviewResponse>('/catalog/card-preview', {
      params: {
        tcgdx_card_id: tcgdxCardId,
        pokewallet_set_code: pokewalletSetCode?.trim() || undefined,
        browse_locale: browseLocale ?? undefined,
      },
    })
    return data
  }

  return {
    browseCatalog,
    browseCatalogFromApi,
    searchCatalogCards,
    listSeries,
    getSeries,
    listSets,
    getSet,
    previewCard,
  }
}
