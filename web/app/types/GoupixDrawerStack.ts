export type GoupixArticleDrawerEntry = {
  kind: 'article'
  articleId: number
}

export type GoupixSealedDrawerEntry = {
  kind: 'sealed'
  sealedId: number
}

export type GoupixDrawerStackEntry = GoupixArticleDrawerEntry | GoupixSealedDrawerEntry

export type GoupixArticleMutationNotice = {
  type: 'updated'
  articleId: number
}

export type GoupixSealedMutationNotice = {
  type: 'updated' | 'deleted'
  sealedId: number
}
