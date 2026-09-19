export type GoupixArticleDrawerEntry = {
  kind: 'article'
  articleId: number
}

export type GoupixDrawerStackEntry = GoupixArticleDrawerEntry

export type GoupixArticleMutationNotice = {
  type: 'updated'
  articleId: number
}
