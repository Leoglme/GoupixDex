import type { Ref } from 'vue'
import type {
  PublishReviewChoice,
  PublishReviewPrompt,
  PublishReviewPromptState,
  PublishReviewRequest,
} from '~/types/PublishReviewPrompt'

let resolvePublishReviewChoice: ((choice: PublishReviewChoice | null) => void) | null = null

/**
 * Demande avant une mise en ligne s'il faut d'abord modifier les fiches, via la modale de `GoupixDexPublishReviewHost`.
 * @returns {PublishReviewPrompt} État de la modale, question et réponse.
 */
export function usePublishReviewPrompt(): PublishReviewPrompt {
  const promptState: Ref<PublishReviewPromptState> = useState(
    'goupix-publish-review-prompt',
    (): PublishReviewPromptState => ({ isOpen: false, request: null }),
  )

  /**
   * Ouvre la question et attend la réponse.
   * @param {PublishReviewRequest} request - Articles et marketplaces concernés.
   * @returns {Promise<PublishReviewChoice | null>} `review` pour modifier d'abord, `publish` pour publier tout de suite, `null` si la modale est fermée.
   */
  function askWhetherToReviewBeforePublishing(request: PublishReviewRequest): Promise<PublishReviewChoice | null> {
    resolvePublishReviewChoice?.(null)
    return new Promise((resolve: (choice: PublishReviewChoice | null) => void): void => {
      resolvePublishReviewChoice = resolve
      promptState.value = { isOpen: true, request }
    })
  }

  /**
   * Ferme la question en transmettant la réponse.
   * @param {PublishReviewChoice | null} choice - Réponse choisie, ou `null` quand la modale est fermée sans choix.
   * @returns {void}
   */
  function answerPublishReviewPrompt(choice: PublishReviewChoice | null): void {
    promptState.value = { isOpen: false, request: null }
    const resolve: ((choice: PublishReviewChoice | null) => void) | null = resolvePublishReviewChoice
    resolvePublishReviewChoice = null
    resolve?.(choice)
  }

  return { promptState, askWhetherToReviewBeforePublishing, answerPublishReviewPrompt }
}
