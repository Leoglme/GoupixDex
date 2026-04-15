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
  purchase_price: number
  sell_price: number | null
  is_sold: boolean
  /** Mis à jour côté serveur après une publication Vinted réussie. */
  published_on_vinted?: boolean
  vinted_published_at?: string | null
  created_at: string
  sold_at: string | null
  images: ArticleImage[]
}

export interface CreateArticleVintedResult {
  published?: boolean
  skipped?: boolean
  detail?: string
  /** Publication lancée en arrière-plan ; suivre ``stream_path`` en SSE. */
  status?: 'running' | 'pending'
  stream_path?: string
  /** Création sur l’API distante ; publication nodriver sur le worker local (Tauri). */
  desktop_local?: boolean
}

export interface CreateArticleResponse {
  article: Article
  vinted: CreateArticleVintedResult
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

export interface ArticleUpdateBody {
  title?: string
  description?: string
  pokemon_name?: string | null
  set_code?: string | null
  card_number?: string | null
  condition?: string | null
  purchase_price?: number
  sell_price?: number | null
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

  async function markSold(id: number, sellPrice: number) {
    const { data } = await $api.patch<Article>(`/articles/${id}/sold`, {
      sell_price: sellPrice
    })
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

  return {
    listArticles,
    getArticle,
    createArticle,
    updateArticle,
    deleteArticle,
    deleteArticlesBulk,
    markSold,
    publishArticleToVinted,
    startVintedBatch,
    getVintedBatchActive
  }
}
