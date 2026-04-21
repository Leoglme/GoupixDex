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
  /** Édition : remet le suivi Vinted à « non publié » dans GoupixDex. */
  clear_vinted_publication?: boolean
  /** Édition : remet le suivi eBay à « non publié » dans GoupixDex. */
  clear_ebay_publication?: boolean
}

export function useArticles() {
  const { $api, $vintedLocal } = useNuxtApp()
  const { isDesktopApp } = useDesktopRuntime()

  function vintedHttp() {
    if (import.meta.client && isDesktopApp.value && $vintedLocal) {
      return $vintedLocal
    }
    return $api
  }

  async function listArticles() {
    const { data } = await $api.get<Article[]>('/articles')
    return data
  }

  async function getArticle(id: number) {
    const { data } = await $api.get<Article>(`/articles/${id}`)
    return data
  }

  async function createArticle(form: FormData) {
    const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' }
    if (
      import.meta.client
      && isDesktopApp.value
      && form.get('publish_to_vinted') === 'true'
    ) {
      headers['X-Goupix-Vinted-Target'] = 'local'
    }
    const { data } = await $api.post<CreateArticleResponse>('/articles', form, { headers })
    return data
  }

  async function updateArticle(id: number, body: ArticleUpdateBody) {
    const { data } = await $api.put<Article>(`/articles/${id}`, body)
    return data
  }

  async function deleteArticle(id: number) {
    await $api.delete(`/articles/${id}`)
  }

  async function deleteArticlesBulk(ids: number[]) {
    const { data } = await $api.post<{ deleted: number, requested: number }>(
      '/articles/bulk-delete',
      { ids }
    )
    return data
  }

  async function markSold(
    id: number,
    body: { sold_price: number, sale_source: 'vinted' | 'ebay' }
  ) {
    const { data } = await $api.patch<Article>(`/articles/${id}/sold`, body)
    return data
  }

  async function publishArticleToVinted(id: number) {
    const { data } = await vintedHttp().post<PublishVintedResponse>(
      `/articles/${id}/publish-vinted`
    )
    return data
  }

  async function startVintedBatch(articleIds: number[]) {
    const { data } = await vintedHttp().post<VintedBatchStartResponse>(
      '/articles/vinted-batch',
      { article_ids: articleIds }
    )
    return data
  }

  async function getVintedBatchActive() {
    const { data } = await vintedHttp().get<VintedBatchActiveResponse>(
      '/articles/vinted-batch/active'
    )
    return data
  }

  async function publishArticleToEbay(id: number) {
    const { data } = await $api.post<PublishEbayResponse>(`/articles/${id}/publish-ebay`)
    return data
  }

  async function startEbayBatch(articleIds: number[]) {
    const { data } = await $api.post<EbayBatchStartResponse>('/articles/ebay-batch', {
      article_ids: articleIds
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
    getVintedBatchActive
  }
}
