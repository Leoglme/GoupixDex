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
  created_at: string
  sold_at: string | null
  images: ArticleImage[]
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
  const { $api } = useNuxtApp()

  async function listArticles() {
    const { data } = await $api.get<Article[]>('/articles')
    return data
  }

  async function getArticle(id: number) {
    const { data } = await $api.get<Article>(`/articles/${id}`)
    return data
  }

  async function createArticle(form: FormData) {
    const { data } = await $api.post<{ article: Article }>('/articles', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return data.article
  }

  async function updateArticle(id: number, body: ArticleUpdateBody) {
    const { data } = await $api.put<Article>(`/articles/${id}`, body)
    return data
  }

  async function deleteArticle(id: number) {
    await $api.delete(`/articles/${id}`)
  }

  async function markSold(id: number, sellPrice: number) {
    const { data } = await $api.patch<Article>(`/articles/${id}/sold`, {
      sell_price: sellPrice
    })
    return data
  }

  return {
    listArticles,
    getArticle,
    createArticle,
    updateArticle,
    deleteArticle,
    markSold
  }
}
