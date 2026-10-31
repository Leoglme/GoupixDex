import type { ArticleUpdateBody } from '~/composables/useArticles'

export type GoupixDexArticleEditDrawerProps = {
  open: boolean
  articleId: number | null
}

export type ArticleFieldChanges = {
  changedFields: ArticleUpdateBody
  hasInvalidField: boolean
}
