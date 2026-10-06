import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type {
  EbayLeboncoinChannels,
  EbayLeboncoinDelist,
  EbayLeboncoinDelistFailure,
  EbayLeboncoinDelistTracker,
} from '~/types/EbayLeboncoinDelist'
import type { LeboncoinListingRemoval, LeboncoinListingRemovalFailure } from '~/types/LeboncoinListingRemoval'

/**
 * Retire les annonces eBay / Leboncoin d'une sélection et partage la progression avec le journal du retrait Vinted.
 * @returns {EbayLeboncoinDelistTracker} Progression du dernier retrait et son lancement.
 */
export function useEbayLeboncoinDelist(): EbayLeboncoinDelistTracker {
  const { bulkDelistChannels } = useArticles()
  const { removeLeboncoinListings } = useLeboncoinListingRemoval()
  const { notifyArticleUpdated } = useGoupixDrawerStack()
  const ebayLeboncoinDelist: Ref<EbayLeboncoinDelist | null> = useState('goupix-ebay-leboncoin-delist', () => null)

  /**
   * Retire les annonces eBay article par article : une requête courte chacune, pour suivre la progression sans dépasser le délai de l'API.
   * @param {Article[]} articles - Articles encore en ligne sur eBay.
   * @param {EbayLeboncoinDelist} delist - Bilan du retrait, mis à jour au fil de l'eau.
   * @returns {Promise<void>} Résolue une fois chaque article traité.
   */
  async function removeEbayListings(articles: Article[], delist: EbayLeboncoinDelist): Promise<void> {
    for (const article of articles) {
      try {
        const response = await bulkDelistChannels({
          article_ids: [article.id],
          vinted: false,
          ebay: true,
          leboncoin: false,
        })
        delist.removedFromEbayCount += response.ebay_removed
        for (const failure of response.ebay_failures) {
          delist.failures.push({ articleId: article.id, articleTitle: article.title, reason: failure.detail })
        }
      } catch (error: unknown) {
        delist.failures.push({ articleId: article.id, articleTitle: article.title, reason: apiErrorMessage(error) })
      }
      delist.processedCount += 1
      notifyArticleUpdated(article.id)
    }
  }

  /**
   * Fait supprimer les annonces Leboncoin par le PC, dans un seul Chrome, et reporte son bilan.
   * @param {Article[]} articles - Articles encore en ligne sur Leboncoin.
   * @param {EbayLeboncoinDelist} delist - Bilan du retrait, complété à la fin du retrait Leboncoin.
   * @returns {Promise<void>} Résolue une fois le PC revenu (ou le suivi abandonné).
   */
  async function removeLeboncoinListingsOnPc(articles: Article[], delist: EbayLeboncoinDelist): Promise<void> {
    try {
      const removal: LeboncoinListingRemoval = await removeLeboncoinListings(articles)
      delist.removedFromLeboncoinCount += removal.removedCount
      delist.failures.push(
        ...removal.failures.map(
          (failure: LeboncoinListingRemovalFailure): EbayLeboncoinDelistFailure => ({
            articleId: failure.articleId,
            articleTitle: failure.articleTitle,
            reason: `Leboncoin — ${failure.reason}`,
          }),
        ),
      )
      if (removal.hasStoppedWaiting) {
        delist.failures.push(
          ...articles.map(
            (article: Article): EbayLeboncoinDelistFailure => ({
              articleId: article.id,
              articleTitle: article.title,
              reason: 'Leboncoin — retrait toujours en cours sur votre PC : vérifiez la fiche dans quelques minutes.',
            }),
          ),
        )
      }
    } catch (error: unknown) {
      delist.failures.push(
        ...articles.map(
          (article: Article): EbayLeboncoinDelistFailure => ({
            articleId: article.id,
            articleTitle: article.title,
            reason: `Leboncoin — ${apiErrorMessage(error)}`,
          }),
        ),
      )
    }
    delist.processedCount += articles.length
  }

  /**
   * Retire les annonces des marketplaces cochées : eBay via l'API, Leboncoin via le PC, en même temps.
   * @param {Article[]} articles - Articles dont retirer les annonces.
   * @param {EbayLeboncoinChannels} channels - Marketplaces cochées hors Vinted (Leboncoin seulement si le PC est joignable).
   * @param {string | null} vintedDelistJobId - Lot Vinted lancé en même temps, dont le journal suit ce retrait.
   * @returns {Promise<EbayLeboncoinDelist>} Le bilan du retrait, échecs compris.
   */
  async function removeEbayLeboncoinListings(
    articles: Article[],
    channels: EbayLeboncoinChannels,
    vintedDelistJobId: string | null,
  ): Promise<EbayLeboncoinDelist> {
    const ebayArticles: Article[] = channels.ebay
      ? articles.filter((article: Article): boolean => Boolean(article.published_on_ebay))
      : []
    const leboncoinArticles: Article[] = channels.leboncoin
      ? articles.filter((article: Article): boolean => Boolean(article.published_on_leboncoin))
      : []
    const delist: EbayLeboncoinDelist = reactive({
      vintedDelistJobId,
      isRunning: true,
      processedCount: 0,
      totalCount: ebayArticles.length + leboncoinArticles.length,
      removedFromEbayCount: 0,
      removedFromLeboncoinCount: 0,
      failures: [],
    })
    ebayLeboncoinDelist.value = delist

    await Promise.all([
      removeEbayListings(ebayArticles, delist),
      leboncoinArticles.length ? removeLeboncoinListingsOnPc(leboncoinArticles, delist) : Promise.resolve(),
    ])

    delist.isRunning = false
    return delist
  }

  return { ebayLeboncoinDelist, removeEbayLeboncoinListings }
}
