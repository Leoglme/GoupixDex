import type { Ref } from 'vue'
import type { Marketplace } from '~/types/Marketplace'

export type PublishReviewChoice = 'review' | 'publish'

export type PublishReviewRequest = {
  subjectLabel: string
  marketplaces: Marketplace[]
}

export type PublishReviewPromptState = {
  isOpen: boolean
  request: PublishReviewRequest | null
}

export type PublishReviewPrompt = {
  promptState: Ref<PublishReviewPromptState>
  askWhetherToReviewBeforePublishing: (request: PublishReviewRequest) => Promise<PublishReviewChoice | null>
  answerPublishReviewPrompt: (choice: PublishReviewChoice | null) => void
}
