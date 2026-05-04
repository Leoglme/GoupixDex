export interface ArticleImage {
  id: number
  image_url: string
  created_at: string
}

export interface Article {
  id: number
  user_id: number
  title: string
  description: string
  pokemon_name: string | null
  set_code: string | null
  card_number: string | null
  condition: string
  is_graded?: boolean
  graded_grader_value_id?: string | null
  graded_grade_value_id?: string | null
  graded_cert_number?: string | null
  purchase_price: number
  sell_price: number | null
  /** Actual proceeds (may differ from listed price if negotiated). */
  sold_price: number | null
  /** Sales channel recorded at checkout. */
  sale_source: 'vinted' | 'ebay' | null
  is_sold: boolean
  /** Updated server-side after a successful Vinted listing. */
  published_on_vinted?: boolean
  vinted_published_at?: string | null
  published_on_ebay?: boolean
  ebay_listing_id?: string | null
  ebay_published_at?: string | null
  created_at: string
  sold_at: string | null
  images: ArticleImage[]
}

export interface CreateArticleVintedResult {
  published?: boolean
  skipped?: boolean
  detail?: string
  /** Publish runs in the background; follow ``stream_path`` via SSE. */
  status?: 'running' | 'pending'
  stream_path?: string
  /** Remote API create; nodriver publish on the local worker (Tauri). */
  desktop_local?: boolean
}

export interface CreateArticleEbayResult {
  published?: boolean
  skipped?: boolean
  detail?: string
  status?: 'running'
  /** Real-time progress (same SSE endpoint as Vinted). */
  stream_path?: string
}

export interface CreateArticleResponse {
  article: Article
  vinted: CreateArticleVintedResult
  ebay?: CreateArticleEbayResult
}

export interface PublishVintedResponse {
  vinted: {
    status: 'running'
    stream_path: string
  }
}

export interface VintedBatchStartResponse {
  job_id: string
  stream_path: string
}

export interface VintedBatchActiveResponse {
  job_id: string | null
  stream_path: string | null
}

export interface EbayBatchStartResponse {
  queued: number
}

export interface PublishEbayResponse {
  ebay: {
    status: 'running'
    stream_path: string
  }
}

export interface ArticleUpdateBody {
  title?: string
  description?: string
  pokemon_name?: string | null
  set_code?: string | null
  card_number?: string | null
  condition?: string | null
  is_graded?: boolean
  graded_grader_value_id?: string | null
  graded_grade_value_id?: string | null
  graded_cert_number?: string | null
  purchase_price?: number
  sell_price?: number | null
  /** Edit: reset Vinted tracking to “unpublished” in GoupixDex. */
  clear_vinted_publication?: boolean
  /** Edit: reset eBay tracking to “unpublished” in GoupixDex. */
  clear_ebay_publication?: boolean
}

/**
 * Article REST CRUD, marketplace publish endpoints, and Vinted worker routing on desktop.
 *
 * @returns HTTP helpers; `vintedHttp()` picks `$vintedLocal` when running inside Tauri with publish intent.
 */
export function useArticles() {
  const { $api, $vintedLocal } = useNuxtApp()
  const { isDesktopApp } = useDesktopRuntime()

  /**
   * Axios instance for Vinted automation — local worker on desktop when available.
   *
   * @returns Axios-like client (`$vintedLocal` or `$api`).
   */
  function vintedHttp() {
    if (import.meta.client && isDesktopApp.value && $vintedLocal) {
      return $vintedLocal
    }
    return $api
  }

  /**
   * GET `/articles` — current user’s inventory.
   *
   * @returns {Promise<Article[]>} Article rows with nested images.
   */
  async function listArticles() {
    const { data } = await $api.get<Article[]>('/articles')
    return data
  }

  /**
   * GET `/articles/:id` — single article detail.
   *
   * @param id - Article primary key.
   * @returns {Promise<Article>} Full article payload.
   */
  async function getArticle(id: number) {
    const { data } = await $api.get<Article>(`/articles/${id}`)
    return data
  }

  /**
   * POST `/articles` — multipart create (+ optional Vinted/eBay publish flags in form).
   *
   * @param form - `FormData` including images and marketplace booleans.
   * @returns {Promise<CreateArticleResponse>} Created article + publish stubs / stream paths.
   */
  async function createArticle(form: FormData) {
    const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' }
    if (import.meta.client && isDesktopApp.value && form.get('publish_to_vinted') === 'true') {
      headers['X-Goupix-Vinted-Target'] = 'local'
    }
    const { data } = await $api.post<CreateArticleResponse>('/articles', form, { headers })
    return data
  }

  /**
   * PUT `/articles/:id` — JSON patch for editable fields.
   *
   * @param id - Article id.
   * @param body - Partial article fields.
   * @returns {Promise<Article>} Updated article row.
   */
  async function updateArticle(id: number, body: ArticleUpdateBody) {
    const { data } = await $api.put<Article>(`/articles/${id}`, body)
    return data
  }

  /**
   * DELETE `/articles/:id`.
   *
   * @param id - Article id.
   * @returns {Promise<void>} Resolves on 2xx.
   */
  async function deleteArticle(id: number) {
    await $api.delete(`/articles/${id}`)
  }

  /**
   * POST `/articles/bulk-delete`.
   *
   * @param ids - Article ids to delete.
   * @returns {Promise<{ deleted: number; requested: number }>} Count summary from the API.
   */
  async function deleteArticlesBulk(ids: number[]) {
    const { data } = await $api.post<{ deleted: number; requested: number }>('/articles/bulk-delete', { ids })
    return data
  }

  /**
   * PATCH `/articles/:id/sold` — record sale price + channel.
   *
   * @param id - Article id.
   * @param payload - `{ sold_price, sale_source }` for the PATCH body.
   * @returns {Promise<Article>} Updated article marked sold.
   */
  async function markSold(id: number, payload: { sold_price: number; sale_source: 'vinted' | 'ebay' }) {
    const { data } = await $api.patch<Article>(`/articles/${id}/sold`, payload)
    return data
  }

  /**
   * POST Vinted publish for one article (SSE stream path in response body).
   *
   * @param id - Article id.
   * @returns {Promise<PublishVintedResponse>} Running job + `stream_path`.
   */
  async function publishArticleToVinted(id: number) {
    const { data } = await vintedHttp().post<PublishVintedResponse>(`/articles/${id}/publish-vinted`)
    return data
  }

  /**
   * POST `/articles/vinted-batch` — enqueue multiple articles for sequential desktop publish.
   *
   * @param articleIds - Ids to include in the batch job.
   * @returns {Promise<VintedBatchStartResponse>} Job id + SSE path.
   */
  async function startVintedBatch(articleIds: number[]) {
    const { data } = await vintedHttp().post<VintedBatchStartResponse>('/articles/vinted-batch', {
      article_ids: articleIds,
    })
    return data
  }

  /**
   * GET `/articles/vinted-batch/active` — resume UI state after reload.
   *
   * @returns {Promise<VintedBatchActiveResponse>} Active job pointer or nulls when idle.
   */
  async function getVintedBatchActive() {
    const { data } = await vintedHttp().get<VintedBatchActiveResponse>('/articles/vinted-batch/active')
    return data
  }

  /**
   * POST eBay publish for one article.
   *
   * @param id - Article id.
   * @returns {Promise<PublishEbayResponse>} Running hub stream reference.
   */
  async function publishArticleToEbay(id: number) {
    const { data } = await $api.post<PublishEbayResponse>(`/articles/${id}/publish-ebay`)
    return data
  }

  /**
   * POST `/articles/ebay-batch` — queue multiple eBay listings server-side.
   *
   * @param articleIds - Article ids.
   * @returns {Promise<EbayBatchStartResponse>} Queue depth hint from the API.
   */
  async function startEbayBatch(articleIds: number[]) {
    const { data } = await $api.post<EbayBatchStartResponse>('/articles/ebay-batch', {
      article_ids: articleIds,
    })
    return data
  }

  return {
    listArticles,
    getArticle,
    createArticle,
    updateArticle,
    deleteArticle,
    deleteArticlesBulk,
    markSold,
    publishArticleToVinted,
    publishArticleToEbay,
    startVintedBatch,
    startEbayBatch,
    getVintedBatchActive,
  }
}
