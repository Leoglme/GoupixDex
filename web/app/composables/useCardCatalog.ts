/** TCGdex-backed catalog API (authenticated proxy through GoupixDex). */

export type CatalogLocale = 'en' | 'fr' | 'ja'

export interface TcgdexSetBrief {
  id: string
  name: string
  logo?: string
  symbol?: string
  cardCount?: { total?: number, official?: number }
}

/** Row from ``GET /catalog/series`` (TCGdex ``/series``). */
export interface TcgdexSeriesBrief {
  id: string
  name: string
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

export interface TcgdexCardInSetBrief {
  id: string
  localId: string
  name: string
  image?: string
  /** Ready-to-use thumbnail URL (``…/low.webp``), set by GoupixDex ``GET /catalog/sets/:id``. */
  image_low?: string
}

export interface TcgdexSetDetail extends TcgdexSetBrief {
  cards?: TcgdexCardInSetBrief[]
  releaseDate?: string
  serie?: { id?: string, name?: string }
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
    names: { en: string, fr: string, ja: string | null }
    set_id: string
    local_id: string
  }
  pokewallet: { set_code: string, card_number: string }
  listing_preview: { title: string, description: string, suggested_price: number | null }
  pricing: {
    cardmarket_eur: number | null
    tcgplayer_usd: number | null
    average_price_eur: number | null
    error: string | null
  }
  image_url_high: string | null
  margin_percent_used: number
  error?: string | null
}

export function useCardCatalog() {
  const { $api } = useNuxtApp()

  async function listSeries(params: { locale: CatalogLocale, name?: string }) {
    const { data } = await $api.get<CatalogSeriesListResponse>('/catalog/series', {
      params: {
        locale: params.locale,
        name: params.name?.trim() || undefined
      }
    })
    return data
  }

  async function getSeries(locale: CatalogLocale, seriesId: string) {
    const { data } = await $api.get<CatalogSeriesDetailResponse>(
      `/catalog/series/${encodeURIComponent(seriesId)}`,
      { params: { locale } }
    )
    return data
  }

  async function listSets(params: {
    locale: CatalogLocale
    page?: number
    perPage?: number
    name?: string
  }) {
    const { data } = await $api.get<CatalogSetsResponse>('/catalog/sets', {
      params: {
        locale: params.locale,
        page: params.page ?? 1,
        per_page: params.perPage ?? 50,
        name: params.name?.trim() || undefined
      }
    })
    return data
  }

  async function getSet(locale: CatalogLocale, setId: string) {
    const { data } = await $api.get<CatalogSetResponse>(`/catalog/sets/${encodeURIComponent(setId)}`, {
      params: { locale }
    })
    return data
  }

  async function previewCard(
    tcgdxCardId: string,
    pokewalletSetCode?: string | null,
    browseLocale?: CatalogLocale | null
  ) {
    const { data } = await $api.get<CatalogCardPreviewResponse>('/catalog/card-preview', {
      params: {
        tcgdx_card_id: tcgdxCardId,
        pokewallet_set_code: pokewalletSetCode?.trim() || undefined,
        browse_locale: browseLocale ?? undefined
      }
    })
    return data
  }

  return { listSeries, getSeries, listSets, getSet, previewCard }
}
