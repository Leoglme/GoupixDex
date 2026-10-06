import type { Article } from '~/composables/useArticles'
import type {
  LeboncoinListingRemoval,
  LeboncoinListingRemovalFailure,
  LeboncoinListingRemovalOutcome,
  LeboncoinListingRemovalStatus,
  LeboncoinListingRemover,
} from '~/types/LeboncoinListingRemoval'

const REMOVAL_STATUS_POLL_INTERVAL_MS: number = 3_000
const CHROME_AND_MY_ADS_OPENING_MS: number = 60_000
const LISTING_DELETION_MS: number = 45_000

/**
 * Supprime des annonces Leboncoin via le PC et suit le retrait jusqu'à son résultat.
 * @returns {LeboncoinListingRemover} Lancement et suivi du retrait.
 */
export function useLeboncoinListingRemoval(): LeboncoinListingRemover {
  const toast = useToast()
  const { startLeboncoinListingRemoval, getLeboncoinListingRemoval } = useArticles()
  const { notifyArticleUpdated } = useGoupixDrawerStack()
  const { openArticle } = useOpenArticleDrawer()

  /**
   * Interroge le PC jusqu'à la fin du retrait ; une erreur passagère du relais ne l'interrompt pas.
   * @param {string} jobId - Retrait lancé sur le PC.
   * @param {number} articleCount - Nombre d'annonces à supprimer, qui allonge l'attente.
   * @returns {Promise<LeboncoinListingRemovalStatus | null>} Le retrait terminé, ou null si le PC n'a pas répondu à temps.
   */
  async function waitForRemovalToFinish(
    jobId: string,
    articleCount: number,
  ): Promise<LeboncoinListingRemovalStatus | null> {
    const deadline: number = Date.now() + CHROME_AND_MY_ADS_OPENING_MS + articleCount * LISTING_DELETION_MS
    while (Date.now() < deadline) {
      await new Promise<void>((resolve: () => void): void => {
        setTimeout(resolve, REMOVAL_STATUS_POLL_INTERVAL_MS)
      })
      const removalStatus: LeboncoinListingRemovalStatus | null = await getLeboncoinListingRemoval(jobId).catch(
        (): null => null,
      )
      if (removalStatus?.finished) {
        return removalStatus
      }
    }
    return null
  }

  /**
   * Lance la suppression des annonces Leboncoin sur le PC puis attend son bilan.
   * @param {Article[]} articles - Articles dont l'annonce Leboncoin doit être supprimée.
   * @returns {Promise<LeboncoinListingRemoval>} Annonces supprimées, échecs et abandon éventuel du suivi.
   * @throws {Error} Quand le PC refuse ou ne reçoit pas la demande.
   */
  async function removeLeboncoinListings(articles: Article[]): Promise<LeboncoinListingRemoval> {
    const { job_id } = await startLeboncoinListingRemoval(articles.map((article: Article): number => article.id))
    const removalStatus: LeboncoinListingRemovalStatus | null = await waitForRemovalToFinish(job_id, articles.length)
    for (const article of articles) {
      notifyArticleUpdated(article.id)
    }
    if (removalStatus === null) {
      return { removedCount: 0, failures: [], hasStoppedWaiting: true }
    }
    const failures: LeboncoinListingRemovalFailure[] = removalStatus.outcomes
      .filter((outcome: LeboncoinListingRemovalOutcome): boolean => !outcome.delisted)
      .map(
        (outcome: LeboncoinListingRemovalOutcome): LeboncoinListingRemovalFailure => ({
          articleId: outcome.article_id,
          articleTitle:
            articles.find((article: Article): boolean => article.id === outcome.article_id)?.title ??
            `Article ${outcome.article_id}`,
          reason: outcome.detail || 'Suppression non confirmée par Leboncoin.',
        }),
      )
    return {
      removedCount: removalStatus.outcomes.length - failures.length,
      failures,
      hasStoppedWaiting: false,
    }
  }

  /**
   * Supprime les annonces Leboncoin via le PC puis annonce le bilan en notifications (échec, réussite, attente).
   * @param {Article[]} articles - Articles dont l'annonce Leboncoin doit être supprimée.
   * @returns {Promise<void>} Résolue une fois le bilan annoncé ; une erreur est annoncée, jamais propagée.
   */
  async function removeLeboncoinListingsAndAnnounce(articles: Article[]): Promise<void> {
    let removal: LeboncoinListingRemoval
    try {
      removal = await removeLeboncoinListings(articles)
    } catch (error: unknown) {
      toast.add({ title: 'Retrait Leboncoin impossible', description: apiErrorMessage(error), color: 'error' })
      return
    }
    const [firstFailure]: LeboncoinListingRemovalFailure[] = removal.failures
    if (firstFailure) {
      toast.add({
        title: 'Retrait Leboncoin échoué',
        description: `${firstFailure.articleTitle} : ${firstFailure.reason}`,
        color: 'error',
        actions: [
          {
            label: 'Ouvrir la fiche',
            color: 'neutral',
            variant: 'outline',
            onClick: (): void => openArticle(firstFailure.articleId),
          },
        ],
      })
    }
    if (removal.removedCount) {
      toast.add({
        title:
          removal.removedCount > 1
            ? `${removal.removedCount} annonces Leboncoin supprimées`
            : 'Annonce Leboncoin supprimée',
        description: 'Leboncoin les retire du site dans les 45 minutes.',
        color: 'success',
      })
    }
    if (removal.hasStoppedWaiting) {
      toast.add({
        title: 'Retrait Leboncoin toujours en cours',
        description: 'Votre PC n’a pas encore terminé : vérifiez la fiche de l’article dans quelques minutes.',
        color: 'neutral',
      })
    }
  }

  return { removeLeboncoinListings, removeLeboncoinListingsAndAnnounce }
}
