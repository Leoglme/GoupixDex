import type { Article } from '~/composables/useArticles'
import type { SoldArticleListingsRemover } from '~/types/SoldArticleListingsRemoval'

const VINTED_REMOVAL_POLL_INTERVAL_MS: number = 4_000
const CHROME_OPENING_MS: number = 60_000
const VINTED_LISTING_DELETION_MS: number = 60_000
const PC_WORKERS_STARTUP_MS: number = 60_000
const MISSED_REMOVALS_CATCH_UP_INTERVAL_MS: number = 10 * 60_000

let missedRemovalsCatchUpTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Après une vente, retire via le PC les annonces restées en ligne sur les autres marketplaces et en annonce le résultat.
 * @returns {SoldArticleListingsRemover} Lancement du retrait.
 */
export function useSoldArticleListingsRemoval(): SoldArticleListingsRemover {
  const toast = useToast()
  const { getArticle, listArticles, vintedUnlistAfterEbaySale, startVintedBatchDelist } = useArticles()
  const { canUseDesktopWorkers, notifyPcUnreachable } = useDesktopWorkers()
  const { removeLeboncoinListingsAndAnnounce } = useLeboncoinListingRemoval()
  const { notifyArticleUpdated } = useGoupixDrawerStack()
  const { openArticle } = useOpenArticleDrawer()

  /**
   * Dit si le retrait Vinted d'un article vendu est encore en cours.
   * @param {Article} article - Article relu après la vente.
   * @returns {boolean} Vrai tant que l'annonce est en ligne sans échec enregistré.
   */
  function hasVintedRemovalInProgress(article: Article): boolean {
    return Boolean(article.published_on_vinted) && !article.cross_vinted_removal_failed
  }

  /**
   * Relit les articles jusqu'à ce que chaque retrait Vinted aboutisse ou échoue (l'échec est enregistré sur la fiche).
   * @param {Article[]} articles - Articles vendus dont l'annonce Vinted est en cours de retrait.
   * @returns {Promise<Article[]>} Dernier état connu de chaque article, retrait terminé ou non.
   */
  async function waitForVintedRemovals(articles: Article[]): Promise<Article[]> {
    const deadline: number = Date.now() + CHROME_OPENING_MS + articles.length * VINTED_LISTING_DELETION_MS
    let latestArticles: Article[] = articles
    while (Date.now() < deadline) {
      await new Promise<void>((resolve: () => void): void => {
        setTimeout(resolve, VINTED_REMOVAL_POLL_INTERVAL_MS)
      })
      try {
        latestArticles = await Promise.all(articles.map((article: Article): Promise<Article> => getArticle(article.id)))
      } catch {
        continue
      }
      if (latestArticles.every((article: Article): boolean => !hasVintedRemovalInProgress(article))) {
        break
      }
    }
    return latestArticles
  }

  /**
   * Lance le retrait Vinted sur le PC puis annonce son résultat.
   * @param {Article[]} articles - Articles vendus encore en ligne sur Vinted.
   * @returns {Promise<void>} Résolue une fois le résultat annoncé.
   */
  async function removeVintedListings(articles: Article[]): Promise<void> {
    try {
      for (const article of articles) {
        await vintedUnlistAfterEbaySale(article.id)
      }
    } catch (error: unknown) {
      toast.add({ title: 'Retrait Vinted impossible', description: apiErrorMessage(error), color: 'error' })
      return
    }
    const latestArticles: Article[] = await waitForVintedRemovals(articles)
    for (const article of articles) {
      notifyArticleUpdated(article.id)
    }
    const failedArticles: Article[] = latestArticles.filter(
      (article: Article): boolean =>
        Boolean(article.published_on_vinted) && Boolean(article.cross_vinted_removal_failed),
    )
    const removedCount: number = latestArticles.filter(
      (article: Article): boolean => !article.published_on_vinted,
    ).length
    const [firstFailedArticle]: Article[] = failedArticles
    if (firstFailedArticle) {
      toast.add({
        title: 'Retrait Vinted échoué',
        description: `${firstFailedArticle.title} : ${firstFailedArticle.cross_vinted_removal_error || 'erreur inconnue'}`,
        color: 'error',
        actions: [
          {
            label: 'Ouvrir la fiche',
            color: 'neutral',
            variant: 'outline',
            onClick: (): void => openArticle(firstFailedArticle.id),
          },
        ],
      })
    }
    if (removedCount) {
      toast.add({
        title: removedCount > 1 ? `${removedCount} annonces Vinted supprimées` : 'Annonce Vinted supprimée',
        color: 'success',
      })
    }
    if (!firstFailedArticle && removedCount < articles.length) {
      toast.add({
        title: 'Retrait Vinted toujours en cours',
        description: 'Votre PC n’a pas encore terminé : vérifiez la fiche de l’article dans quelques minutes.',
        color: 'neutral',
      })
    }
  }

  /**
   * Fait retirer par le PC des annonces Vinted et Leboncoin restées en ligne après une vente, puis en annonce le résultat.
   * @param {Article[]} vintedArticles - Articles vendus dont l'annonce Vinted est à retirer.
   * @param {Article[]} leboncoinArticles - Articles vendus dont l'annonce Leboncoin est à retirer.
   * @returns {Promise<void>} Résolue une fois chaque résultat annoncé.
   */
  async function removeVintedAndLeboncoinListings(
    vintedArticles: Article[],
    leboncoinArticles: Article[],
  ): Promise<void> {
    const marketplaceLabels: string[] = [
      ...(vintedArticles.length ? ['Vinted'] : []),
      ...(leboncoinArticles.length ? ['Leboncoin'] : []),
    ]
    if (!marketplaceLabels.length) {
      return
    }

    const marketplacesLabel: string = marketplaceLabels.join(' et ')
    if (!canUseDesktopWorkers.value) {
      toast.add({
        title: `Annonce ${marketplacesLabel} encore en ligne`,
        description:
          'Votre PC la retirera dès que GoupixDex y sera ouvert ; elle reste listée dans Mes articles, onglet Vendus.',
        color: 'warning',
      })
      return
    }

    toast.add({
      title: 'Retrait lancé sur votre PC',
      description: `Suppression de l’annonce ${marketplacesLabel} en cours…`,
      color: 'neutral',
    })
    await Promise.all([
      vintedArticles.length ? removeVintedListings(vintedArticles) : Promise.resolve(),
      leboncoinArticles.length ? removeLeboncoinListingsAndAnnounce(leboncoinArticles) : Promise.resolve(),
    ])
  }

  /**
   * Retire via le PC les annonces Vinted / Leboncoin encore en ligne d'articles qui viennent d'être vendus.
   * @param {Article[]} soldArticles - Articles tels que renvoyés par l'enregistrement de la vente.
   * @returns {void}
   */
  function removeListingsLeftOnline(soldArticles: Article[]): void {
    removeVintedAndLeboncoinListings(
      soldArticles.filter((article: Article): boolean => Boolean(article.pending_vinted_unlist)),
      soldArticles.filter((article: Article): boolean => Boolean(article.pending_leboncoin_unlist)),
    )
  }

  /**
   * Lit les articles vendus dont une annonce Vinted ou Leboncoin est encore en ligne, échecs de retrait compris.
   * @returns {Promise<Article[]>} Ces articles, du plus récent au plus ancien.
   */
  async function fetchArticlesWithListingsLeftOnline(): Promise<Article[]> {
    const articles: Article[] = await listArticles()
    return articles.filter(
      (article: Article): boolean =>
        Boolean(article.pending_vinted_unlist) || Boolean(article.pending_leboncoin_unlist),
    )
  }

  /**
   * Fait retirer par le PC toutes les annonces restées en ligne après une vente, puis ouvre le journal du retrait Vinted.
   * @param {Article[]} articlesWithListingsLeftOnline - Articles vendus dont une annonce Vinted ou Leboncoin est encore en ligne.
   * @returns {Promise<void>} Résolue une fois les retraits lancés.
   * @throws {Error} Quand le PC refuse ou ne reçoit pas le retrait Vinted.
   */
  async function removeEveryListingLeftOnline(articlesWithListingsLeftOnline: Article[]): Promise<void> {
    if (!canUseDesktopWorkers.value) {
      notifyPcUnreachable('La suppression des annonces')
      return
    }

    const leboncoinArticles: Article[] = articlesWithListingsLeftOnline.filter((article: Article): boolean =>
      Boolean(article.pending_leboncoin_unlist),
    )
    const vintedArticleIds: number[] = articlesWithListingsLeftOnline
      .filter((article: Article): boolean => Boolean(article.pending_vinted_unlist))
      .map((article: Article): number => article.id)
    if (leboncoinArticles.length) {
      removeLeboncoinListingsAndAnnounce(leboncoinArticles)
    }
    if (!vintedArticleIds.length) {
      return
    }

    const { job_id } = await startVintedBatchDelist(vintedArticleIds)
    await navigateTo({
      path: '/articles/listing-logs',
      query: { job: job_id, after: 'delist', back: '/articles/sold' },
    })
  }

  /**
   * Retire les annonces restées en ligne dont le retrait n'a jamais été tenté, le PC étant éteint au moment de la vente.
   * @returns {Promise<void>} Résolue une fois les résultats annoncés, ou tout de suite s'il n'y a rien à retirer.
   */
  async function catchUpMissedListingRemovals(): Promise<void> {
    const articles: Article[] = await listArticles().catch((): Article[] => [])
    await removeVintedAndLeboncoinListings(
      articles.filter(
        (article: Article): boolean => Boolean(article.pending_vinted_unlist) && !article.cross_vinted_removal_failed,
      ),
      articles.filter(
        (article: Article): boolean =>
          Boolean(article.pending_leboncoin_unlist) && !article.cross_leboncoin_removal_failed,
      ),
    )
  }

  /**
   * Programme le prochain rattrapage des retraits manqués, puis les suivants tant qu'il n'est pas arrêté.
   * @param {number} delayMs - Attente avant ce rattrapage.
   * @returns {void}
   */
  function scheduleMissedListingRemovalsCatchUp(delayMs: number): void {
    missedRemovalsCatchUpTimer = setTimeout((): void => {
      catchUpMissedListingRemovals().finally((): void => {
        if (missedRemovalsCatchUpTimer) {
          scheduleMissedListingRemovalsCatchUp(MISSED_REMOVALS_CATCH_UP_INTERVAL_MS)
        }
      })
    }, delayMs)
  }

  /**
   * Lance dans l'app du PC le rattrapage des retraits manqués : une minute après son démarrage, puis toutes les 10 minutes.
   * @returns {void}
   */
  function startMissedListingRemovalsCatchUp(): void {
    if (missedRemovalsCatchUpTimer) {
      return
    }
    scheduleMissedListingRemovalsCatchUp(PC_WORKERS_STARTUP_MS)
  }

  /**
   * Arrête le rattrapage des retraits manqués.
   * @returns {void}
   */
  function stopMissedListingRemovalsCatchUp(): void {
    if (missedRemovalsCatchUpTimer) {
      clearTimeout(missedRemovalsCatchUpTimer)
      missedRemovalsCatchUpTimer = null
    }
  }

  return {
    removeListingsLeftOnline,
    fetchArticlesWithListingsLeftOnline,
    removeEveryListingLeftOnline,
    startMissedListingRemovalsCatchUp,
    stopMissedListingRemovalsCatchUp,
  }
}
