import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { ListingPublishStart } from '~/composables/useMarketplacePublishing'
import type { ArticlePublication, ArticlePublicationQueue } from '~/types/ArticlePublicationQueue'
import type { Marketplace } from '~/types/Marketplace'
import { MARKETPLACE_NAMES } from '~/utils/marketplaces'

/**
 * File de publication d'articles : chaque marketplace publie un article après l'autre, pour enchaîner les mises en ligne sans attendre.
 * @param {(articleId: number) => void} onArticlePublicationFinished - Appelée à la fin de chaque publication d'un article, réussie ou non.
 * @returns {ArticlePublicationQueue} Publications en attente ou en cours, ajout à la file et marketplaces en cours d'un article.
 */
export function useArticlePublicationQueue(
  onArticlePublicationFinished: (articleId: number) => void,
): ArticlePublicationQueue {
  const toast = useToast()
  const { getArticle } = useArticles()
  const { startArticlePublish } = useMarketplacePublishing()
  const publishStreamByMarketplace: Record<Marketplace, ReturnType<typeof useVintedPublishStream>> = {
    vinted: useVintedPublishStream(),
    ebay: useVintedPublishStream(),
    leboncoin: useVintedPublishStream(),
  }
  const marketplacesPublishingNow: Set<Marketplace> = new Set()

  const pendingPublications: Ref<ArticlePublication[]> = ref([])

  /**
   * Vrai quand la publication de l'article sur cette marketplace attend déjà dans la file ou est en cours.
   * @param {number} articleId - Article à publier.
   * @param {Marketplace} marketplace - Marketplace visée.
   * @returns {boolean} Vrai si elle est déjà dans la file.
   */
  function isPublicationPending(articleId: number, marketplace: Marketplace): boolean {
    return pendingPublications.value.some(
      (publication: ArticlePublication): boolean =>
        publication.articleId === articleId && publication.marketplace === marketplace,
    )
  }

  /**
   * Ajoute la publication d'un article à la file de chaque marketplace demandée, puis lance celles qui sont libres.
   * @param {number} articleId - Article à publier.
   * @param {Marketplace[]} marketplaces - Marketplaces visées.
   * @returns {void}
   */
  function queueArticlePublication(articleId: number, marketplaces: Marketplace[]): void {
    const newPublications: ArticlePublication[] = marketplaces
      .filter((marketplace: Marketplace): boolean => !isPublicationPending(articleId, marketplace))
      .map((marketplace: Marketplace): ArticlePublication => ({ articleId, marketplace }))
    pendingPublications.value = [...pendingPublications.value, ...newPublications]
    for (const marketplace of marketplaces) {
      publishNextArticle(marketplace)
    }
  }

  /**
   * Publie le prochain article en attente sur une marketplace, si elle ne publie pas déjà, puis passe au suivant.
   * @param {Marketplace} marketplace - Marketplace dont la file avance.
   * @returns {Promise<void>} Résolue quand la file de cette marketplace est vide.
   */
  async function publishNextArticle(marketplace: Marketplace): Promise<void> {
    const nextPublication: ArticlePublication | undefined = pendingPublications.value.find(
      (publication: ArticlePublication): boolean => publication.marketplace === marketplace,
    )
    if (!nextPublication || marketplacesPublishingNow.has(marketplace)) {
      return
    }
    marketplacesPublishingNow.add(marketplace)
    try {
      await publishArticle(nextPublication)
    } finally {
      marketplacesPublishingNow.delete(marketplace)
      pendingPublications.value = pendingPublications.value.filter(
        (publication: ArticlePublication): boolean => publication !== nextPublication,
      )
      onArticlePublicationFinished(nextPublication.articleId)
      publishNextArticle(marketplace)
    }
  }

  /**
   * Lance la publication d'un article sur une marketplace et suit sa progression jusqu'au message de fin.
   * @param {ArticlePublication} publication - Article et marketplace à publier.
   * @returns {Promise<void>} Résolue quand la publication est terminée, ou n'a pas pu démarrer (toast affiché).
   */
  async function publishArticle(publication: ArticlePublication): Promise<void> {
    try {
      const article: Article = await getArticle(publication.articleId)
      const listingPublish: ListingPublishStart | null = await startArticlePublish(article, publication.marketplace)
      if (listingPublish) {
        await publishStreamByMarketplace[publication.marketplace].followStream(listingPublish.streamPath, 'list', {
          sseBase: listingPublish.sseBase,
          localWorker: listingPublish.localWorker,
        })
      }
    } catch (error: unknown) {
      toast.add({
        title: `Publication ${MARKETPLACE_NAMES[publication.marketplace]}`,
        description: apiErrorMessage(error),
        color: 'warning',
      })
    }
  }

  /**
   * Marketplaces où un article attend sa publication ou est en train d'être publié.
   * @param {number} articleId - Article affiché.
   * @returns {Marketplace[]} Ses marketplaces en attente ou en cours.
   */
  function publishingMarketplacesOfArticle(articleId: number): Marketplace[] {
    return pendingPublications.value
      .filter((publication: ArticlePublication): boolean => publication.articleId === articleId)
      .map((publication: ArticlePublication): Marketplace => publication.marketplace)
  }

  return { pendingPublications, queueArticlePublication, publishingMarketplacesOfArticle }
}
