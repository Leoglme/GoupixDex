import type { Article } from '~/composables/useArticles'

export type LeboncoinListingRemovalOutcome = {
  article_id: number
  delisted: boolean
  detail: string | null
}

export type LeboncoinListingRemovalStart = {
  job_id: string
}

export type LeboncoinListingRemovalStatus = {
  finished: boolean
  outcomes: LeboncoinListingRemovalOutcome[]
}

export type LeboncoinListingRemovalFailure = {
  articleId: number
  articleTitle: string
  reason: string
}

export type LeboncoinListingRemoval = {
  removedCount: number
  failures: LeboncoinListingRemovalFailure[]
  hasStoppedWaiting: boolean
}

export type LeboncoinListingRemover = {
  removeLeboncoinListings: (articles: Article[]) => Promise<LeboncoinListingRemoval>
  removeLeboncoinListingsAndAnnounce: (articles: Article[]) => Promise<void>
}
