import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { ArticleMarketplacePublication } from '~/types/ArticleMarketplacePublication'
import type { Marketplace } from '~/types/Marketplace'
import { MARKETPLACE_NAMES } from '~/utils/marketplaces'

/**
 * Publie un article sur des marketplaces et suit chaque publication jusqu'à son message de fin.
 * @returns {ArticleMarketplacePublication} Marketplaces en cours de publication et lancement des publications.
 */
export function useArticleMarketplacePublication(): ArticleMarketplacePublication {
  const toast = useToast()
  const { startArticlePublish } = useMarketplacePublishing()
  const publishStreamByMarketplace: Record<Marketplace, ReturnType<typeof useVintedPublishStream>> = {
    vinted: useVintedPublishStream(),
    ebay: useVintedPublishStream(),
    leboncoin: useVintedPublishStream(),
  }

  const publishingMarketplaces: Ref<Marketplace[]> = ref([])

  /**
   * Lance la publication de l'article sur une marketplace puis suit sa progression jusqu'au bout.
   * @param {Article} article - Article à publier.
   * @param {Marketplace} marketplace - Marketplace visée.
   * @returns {Promise<void>} Résolue quand la publication est terminée (ou n'a pas démarré).
   */
  async function publishArticleOnMarketplace(article: Article, marketplace: Marketplace): Promise<void> {
    if (publishingMarketplaces.value.includes(marketplace)) {
      return
    }
    publishingMarketplaces.value = [...publishingMarketplaces.value, marketplace]
    try {
      const listingPublish = await startArticlePublish(article, marketplace)
      if (!listingPublish) {
        return
      }
      toast.add({
        title: `Publication ${MARKETPLACE_NAMES[marketplace]} lancée`,
        description: 'Un message confirmera la mise en ligne.',
      })
      await publishStreamByMarketplace[marketplace].followStream(listingPublish.streamPath, 'list', {
        sseBase: listingPublish.sseBase,
        localWorker: listingPublish.localWorker,
      })
    } catch (error: unknown) {
      toast.add({
        title: `Publication ${MARKETPLACE_NAMES[marketplace]}`,
        description: apiErrorMessage(error),
        color: 'warning',
      })
    } finally {
      publishingMarketplaces.value = publishingMarketplaces.value.filter(
        (publishingMarketplace: Marketplace): boolean => publishingMarketplace !== marketplace,
      )
    }
  }

  /**
   * Publie l'article sur toutes les marketplaces demandées en même temps : chacune a son propre worker.
   * @param {Article} article - Article à publier.
   * @param {Marketplace[]} marketplaces - Marketplaces visées.
   * @returns {Promise<void>} Résolue quand toutes les publications sont terminées.
   */
  async function publishArticleOnMarketplaces(article: Article, marketplaces: Marketplace[]): Promise<void> {
    await Promise.all(
      marketplaces.map((marketplace: Marketplace): Promise<void> => publishArticleOnMarketplace(article, marketplace)),
    )
  }

  return { publishingMarketplaces, publishArticleOnMarketplaces }
}
