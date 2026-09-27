import type { Ref } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import type { Article } from '~/composables/useArticles'
import type { ListingProgressLocalWorker, ListingProgressSseBase } from '~/composables/useVintedPublishStream'
import type { Marketplace, MarketplaceSetupIssues } from '~/types/Marketplace'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'
import { findMarketplaceSetupIssues, MARKETPLACE_NAMES } from '~/utils/marketplaces'

export type ListingPublishStart = {
  streamPath: string
  sseBase: ListingProgressSseBase
  localWorker: ListingProgressLocalWorker
  journalLocation: RouteLocationRaw
}

const SETTINGS_LOADING_ISSUE: string = 'Chargement des réglages…'
const SETTINGS_UNREADABLE_ISSUE: string = 'Réglages indisponibles : rechargez la page.'

/**
 * Réglage qui empêche de publier sur chaque marketplace, partagé entre les écrans.
 * @returns {Ref<MarketplaceSetupIssues>} Le réglage manquant par marketplace, ou null quand elle est prête.
 */
export function useMarketplaceSetupIssues(): Ref<MarketplaceSetupIssues> {
  return useState(
    'goupix-marketplace-setup-issues',
    (): MarketplaceSetupIssues => ({
      vinted: SETTINGS_LOADING_ISSUE,
      ebay: SETTINGS_LOADING_ISSUE,
      leboncoin: SETTINGS_LOADING_ISSUE,
    }),
  )
}

/**
 * Mise en ligne d'un article : canaux disponibles et démarrage de la publication.
 *
 * @returns {object} Disponibilité des canaux et réglages manquants (`useState` partagés), `loadMarketplaceAvailability`, `ensureLeboncoinPublishReady` et `startArticlePublish`.
 */
export function useMarketplacePublishing() {
  const { getSettings } = useSettings()
  const { publishArticleToVinted, publishArticleToEbay, publishArticleToLeboncoin } = useArticles()
  const { canUseDesktopWorkers } = useDesktopWorkers()
  const toast = useToast()

  const isVintedChannelEnabled: Ref<boolean> = useState('goupix-vinted-channel-enabled', () => false)
  const canPublishOnEbay: Ref<boolean> = useState('goupix-ebay-publish-available', () => false)
  const canPublishOnLeboncoin: Ref<boolean> = useState('goupix-leboncoin-publish-available', () => false)
  const marketplaceSetupIssues: Ref<MarketplaceSetupIssues> = useMarketplaceSetupIssues()

  /**
   * Lit les paramètres pour savoir sur quelles marketplaces l'utilisateur peut publier.
   *
   * @returns {Promise<void>} Résolue une fois les drapeaux à jour (tous faux si les paramètres sont illisibles).
   */
  async function loadMarketplaceAvailability(): Promise<void> {
    try {
      marketplaceSetupIssues.value = findMarketplaceSetupIssues(await getSettings())
    } catch {
      marketplaceSetupIssues.value = {
        vinted: SETTINGS_UNREADABLE_ISSUE,
        ebay: SETTINGS_UNREADABLE_ISSUE,
        leboncoin: SETTINGS_UNREADABLE_ISSUE,
      }
    }
    isVintedChannelEnabled.value = marketplaceSetupIssues.value.vinted === null
    canPublishOnEbay.value = marketplaceSetupIssues.value.ebay === null
    canPublishOnLeboncoin.value = marketplaceSetupIssues.value.leboncoin === null
  }

  /**
   * Vérifie l'adresse d'expédition requise par Leboncoin, sinon ouvre le profil pour la compléter.
   *
   * @returns {Promise<boolean>} Vrai si la publication Leboncoin peut partir.
   */
  async function ensureLeboncoinPublishReady(): Promise<boolean> {
    try {
      const settings = await getSettings()
      if (settings.sender_address_complete) {
        return true
      }
    } catch {
      /* fall through */
    }
    toast.add({
      title: 'Adresse expéditeur requise',
      description: 'Complétez votre adresse dans Mon profil (menu compte) avant de publier sur Leboncoin.',
      color: 'warning',
    })
    const { openProfileDrawer } = useProfileDrawer()
    openProfileDrawer()
    return false
  }

  /**
   * Lance la publication d'un article sur une marketplace ; les échecs sont annoncés par un toast.
   *
   * @param article - Article à publier.
   * @param marketplace - Marketplace visée.
   * @returns {Promise<ListingPublishStart | null>} Flux de progression et journal à suivre, ou `null` si rien n'a démarré.
   */
  async function startArticlePublish(article: Article, marketplace: Marketplace): Promise<ListingPublishStart | null> {
    if (marketplace !== 'ebay' && !canUseDesktopWorkers.value) {
      toast.add({
        title: 'Ouvrez GoupixDex sur votre PC',
        description: `La mise en ligne ${MARKETPLACE_NAMES[marketplace]} s’exécute sur votre PC : lancez GoupixDex sur votre ordinateur, puis réessayez.`,
        color: 'warning',
      })
      return null
    }
    if (marketplace === 'leboncoin' && !(await ensureLeboncoinPublishReady())) {
      return null
    }
    try {
      if (marketplace === 'vinted') {
        const { vinted } = await publishArticleToVinted(article.id)
        return listingPublishStart(article.id, vinted.stream_path, 'local', 'vinted', { progress: 'local' })
      }
      if (marketplace === 'ebay') {
        const { ebay } = await publishArticleToEbay(article.id)
        return listingPublishStart(article.id, ebay.stream_path, 'api', 'vinted', {})
      }
      const { leboncoin } = await publishArticleToLeboncoin(article.id)
      return listingPublishStart(article.id, leboncoin.stream_path, 'local', 'leboncoin', {
        progress: 'local',
        worker: 'leboncoin',
      })
    } catch (e) {
      toast.add({
        title: `Publication ${MARKETPLACE_NAMES[marketplace]} impossible`,
        description: apiErrorMessage(e),
        color: 'error',
      })
      return null
    }
  }

  /**
   * Décrit une publication qui a démarré : son flux de progression et son journal.
   *
   * @param articleId - Article publié.
   * @param streamPath - Chemin SSE renvoyé par le worker ou l'API (vide si la réponse est inattendue).
   * @param sseBase - Hôte du flux : API distante ou worker local.
   * @param localWorker - Worker local qui sert le flux.
   * @param journalQuery - Paramètres du journal propres à la marketplace.
   * @returns {ListingPublishStart | null} `null` (avec un toast) quand la réponse ne donne aucun flux.
   */
  function listingPublishStart(
    articleId: number,
    streamPath: string | undefined,
    sseBase: ListingProgressSseBase,
    localWorker: ListingProgressLocalWorker,
    journalQuery: Record<string, string>,
  ): ListingPublishStart | null {
    if (!streamPath) {
      toast.add({
        title: 'Publication',
        description: 'Réponse inattendue : aucun suivi de progression disponible.',
        color: 'warning',
      })
      return null
    }
    return {
      streamPath,
      sseBase,
      localWorker,
      journalLocation: { path: '/articles/listing-logs', query: { article: String(articleId), ...journalQuery } },
    }
  }

  return {
    isVintedChannelEnabled,
    canPublishOnEbay,
    canPublishOnLeboncoin,
    marketplaceSetupIssues,
    loadMarketplaceAvailability,
    ensureLeboncoinPublishReady,
    startArticlePublish,
  }
}
