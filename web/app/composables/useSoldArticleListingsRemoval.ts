import type { Article } from '~/composables/useArticles'
import type { SoldArticleListingsRemover } from '~/types/SoldArticleListingsRemoval'

const VINTED_REMOVAL_POLL_INTERVAL_MS: number = 4_000
const CHROME_OPENING_MS: number = 60_000
const VINTED_LISTING_DELETION_MS: number = 60_000

/**
 * Après une vente, retire via le PC les annonces restées en ligne sur les autres marketplaces et en annonce le résultat.
 * @returns {SoldArticleListingsRemover} Lancement du retrait.
 */
export function useSoldArticleListingsRemoval(): SoldArticleListingsRemover {
  const toast = useToast()
  const { getArticle, vintedUnlistAfterEbaySale } = useArticles()
  const { canUseDesktopWorkers } = useDesktopWorkers()
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
   * Retire via le PC les annonces Vinted / Leboncoin encore en ligne d'articles qui viennent d'être vendus.
   * @param {Article[]} soldArticles - Articles tels que renvoyés par l'enregistrement de la vente.
   * @returns {void}
   */
  function removeListingsLeftOnline(soldArticles: Article[]): void {
    const vintedArticles: Article[] = soldArticles.filter((article: Article): boolean =>
      Boolean(article.pending_vinted_unlist),
    )
    const leboncoinArticles: Article[] = soldArticles.filter((article: Article): boolean =>
      Boolean(article.pending_leboncoin_unlist),
    )
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
          'Ouvrez GoupixDex sur votre PC, puis retirez-la depuis la fiche de l’article (Mes articles, onglet Vendus).',
        color: 'warning',
      })
      return
    }

    toast.add({
      title: 'Retrait lancé sur votre PC',
      description: `Suppression de l’annonce ${marketplacesLabel} en cours…`,
      color: 'neutral',
    })
    if (vintedArticles.length) {
      removeVintedListings(vintedArticles)
    }
    if (leboncoinArticles.length) {
      removeLeboncoinListingsAndAnnounce(leboncoinArticles)
    }
  }

  return { removeListingsLeftOnline }
}
