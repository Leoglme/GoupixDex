import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type {
  EbayLeboncoinChannels,
  EbayLeboncoinDelist,
  EbayLeboncoinDelistTracker,
} from '~/types/EbayLeboncoinDelist'

/**
 * Retire les annonces eBay / Leboncoin d'une sélection et partage la progression avec le journal du retrait Vinted.
 * @returns {EbayLeboncoinDelistTracker} Progression du dernier retrait et son lancement.
 */
export function useEbayLeboncoinDelist(): EbayLeboncoinDelistTracker {
  const { bulkDelistChannels } = useArticles()
  const { notifyArticleUpdated } = useGoupixDrawerStack()
  const ebayLeboncoinDelist: Ref<EbayLeboncoinDelist | null> = useState('goupix-ebay-leboncoin-delist', () => null)

  /**
   * Retire les annonces article par article : une requête courte chacun, pour suivre la progression sans dépasser le délai de l'API.
   * @param {Article[]} articles - Articles dont retirer les annonces.
   * @param {EbayLeboncoinChannels} channels - Marketplaces cochées hors Vinted.
   * @param {string | null} vintedDelistJobId - Lot Vinted lancé en même temps, dont le journal suit ce retrait.
   * @returns {Promise<EbayLeboncoinDelist>} Le bilan du retrait, échecs compris.
   */
  async function removeEbayLeboncoinListings(
    articles: Article[],
    channels: EbayLeboncoinChannels,
    vintedDelistJobId: string | null,
  ): Promise<EbayLeboncoinDelist> {
    const delist: EbayLeboncoinDelist = reactive({
      vintedDelistJobId,
      isRunning: true,
      processedCount: 0,
      totalCount: articles.length,
      removedFromEbayCount: 0,
      removedFromLeboncoinCount: 0,
      failures: [],
    })
    ebayLeboncoinDelist.value = delist

    for (const article of articles) {
      try {
        const response = await bulkDelistChannels({
          article_ids: [article.id],
          vinted: false,
          ebay: channels.ebay,
          leboncoin: channels.leboncoin,
        })
        delist.removedFromEbayCount += response.ebay_removed
        delist.removedFromLeboncoinCount += response.leboncoin_cleared
        for (const failure of response.ebay_failures) {
          delist.failures.push({ articleId: article.id, articleTitle: article.title, reason: failure.detail })
        }
      } catch (error: unknown) {
        delist.failures.push({ articleId: article.id, articleTitle: article.title, reason: apiErrorMessage(error) })
      }
      delist.processedCount += 1
      notifyArticleUpdated(article.id)
    }

    delist.isRunning = false
    return delist
  }

  return { ebayLeboncoinDelist, removeEbayLeboncoinListings }
}
