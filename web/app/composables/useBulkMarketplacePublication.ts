import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { ArticleFinder, BulkMarketplacePublication } from '~/types/BulkMarketplacePublication'
import type { Marketplace } from '~/types/Marketplace'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'
import { useMarketplacePublishing } from '~/composables/useMarketplacePublishing'

/**
 * Publie ensemble plusieurs articles sur les marketplaces choisies (lot Vinted, file eBay, lot Leboncoin) puis ouvre le journal.
 * @param {ArticleFinder} findArticle - Article chargé pour un identifiant, qui décide de son éligibilité à chaque marketplace.
 * @param {() => Promise<void>} [onPublicationsLaunched] - Appelée une fois les publications lancées (rafraîchir une liste…).
 * @returns {BulkMarketplacePublication} Lancement de la publication et son état.
 */
export function useBulkMarketplacePublication(
  findArticle: ArticleFinder,
  onPublicationsLaunched?: () => Promise<void>,
): BulkMarketplacePublication {
  const { startVintedBatch, startLeboncoinBatch, startEbayBatch } = useArticles()
  const toast = useToast()
  const { canUseDesktopWorkers, notifyPcUnreachable } = useDesktopWorkers()
  const { ensureLeboncoinPublishReady } = useMarketplacePublishing()

  const isPublishingInBulk: Ref<boolean> = ref(false)

  /**
   * Vrai quand l'article a au moins une photo hébergée en HTTPS, exigée par eBay.
   * @param {Article} article - Article à publier.
   * @returns {boolean} Vrai si une photo commence par `https://`.
   */
  function hasHttpsImage(article: Article): boolean {
    return article.images?.some((image) => (image.image_url || '').startsWith('https://')) ?? false
  }

  /**
   * Articles publiables sur Vinted : non vendus, avec au moins une photo.
   * @param {number[]} articleIds - Articles à publier.
   * @returns {number[]} Ceux que Vinted acceptera.
   */
  function eligibleIdsForVinted(articleIds: number[]): number[] {
    return articleIds.filter((articleId: number): boolean => {
      const article: Article | undefined = findArticle(articleId)
      return Boolean(article && !article.is_sold && (article.images?.length ?? 0) > 0)
    })
  }

  /**
   * Articles publiables sur eBay : non vendus, pas déjà sur eBay, avec une photo HTTPS.
   * @param {number[]} articleIds - Articles à publier.
   * @returns {number[]} Ceux qu'eBay acceptera.
   */
  function eligibleIdsForEbay(articleIds: number[]): number[] {
    return articleIds.filter((articleId: number): boolean => {
      const article: Article | undefined = findArticle(articleId)
      return Boolean(article && !article.is_sold && !(article.published_on_ebay ?? false) && hasHttpsImage(article))
    })
  }

  /**
   * Articles publiables à la fois sur Vinted et sur eBay.
   * @param {number[]} articleIds - Articles à publier.
   * @returns {number[]} Ceux que les deux marketplaces accepteront.
   */
  function eligibleIdsForVintedAndEbay(articleIds: number[]): number[] {
    const vintedIds: Set<number> = new Set(eligibleIdsForVinted(articleIds))
    return eligibleIdsForEbay(articleIds).filter((articleId: number): boolean => vintedIds.has(articleId))
  }

  /**
   * Lance le lot Vinted des articles éligibles et ouvre son journal.
   * @param {number[]} articleIds - Articles à publier.
   * @param {Record<string, string>} journalQuery - Autres lots à suivre dans le même journal.
   * @returns {Promise<boolean>} Vrai si le journal a été ouvert.
   */
  async function publishOnVinted(articleIds: number[], journalQuery: Record<string, string>): Promise<boolean> {
    const eligibleIds: number[] = eligibleIdsForVinted(articleIds)
    if (!eligibleIds.length) {
      toast.add({
        title: 'Sélection invalide',
        description: 'Choisissez des articles non vendus avec au moins une photo.',
        color: 'warning',
      })
      return false
    }
    if (!canUseDesktopWorkers.value) {
      notifyPcUnreachable('La mise en ligne groupée Vinted')
      return false
    }
    if (eligibleIds.length < articleIds.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles non vendus avec photos sont inclus dans le lot.',
        color: 'warning',
      })
    }
    isPublishingInBulk.value = true
    try {
      const { job_id, stream_path } = await startVintedBatch(eligibleIds)
      if (job_id && stream_path) {
        await navigateTo({ path: '/articles/listing-logs', query: { job: job_id, ...journalQuery } })
        return true
      }
      toast.add({ title: 'Lot Vinted', description: 'Réponse inattendue (pas de job).', color: 'warning' })
      await onPublicationsLaunched?.()
    } catch (error: unknown) {
      toast.add({ title: 'Impossible de lancer le lot Vinted', description: apiErrorMessage(error), color: 'error' })
    } finally {
      isPublishingInBulk.value = false
    }
    return false
  }

  /**
   * Met en file les publications eBay des articles éligibles et ouvre le journal du premier.
   * @param {number[]} articleIds - Articles à publier.
   * @param {Record<string, string>} journalQuery - Autres lots à suivre dans le même journal.
   * @returns {Promise<boolean>} Vrai si le journal a été ouvert.
   */
  async function publishOnEbay(articleIds: number[], journalQuery: Record<string, string>): Promise<boolean> {
    const eligibleIds: number[] = eligibleIdsForEbay(articleIds)
    if (!eligibleIds.length) {
      toast.add({
        title: 'Sélection invalide',
        description: 'Choisissez des articles non vendus, pas déjà sur eBay, avec au moins une image en HTTPS.',
        color: 'warning',
      })
      return false
    }
    if (eligibleIds.length < articleIds.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles éligibles pour eBay (image HTTPS, pas déjà publié) sont inclus.',
        color: 'warning',
      })
    }
    isPublishingInBulk.value = true
    try {
      const { queued } = await startEbayBatch(eligibleIds)
      toast.add({
        title: 'Mise en ligne eBay',
        description: `${queued} publication(s) mise(s) en file d’attente (traitement séquentiel).`,
        color: 'success',
      })
      await navigateTo({ path: '/articles/listing-logs', query: { article: String(eligibleIds[0]), ...journalQuery } })
      await onPublicationsLaunched?.()
      return true
    } catch (error: unknown) {
      toast.add({ title: 'Impossible de lancer le lot eBay', description: apiErrorMessage(error), color: 'error' })
    } finally {
      isPublishingInBulk.value = false
    }
    return false
  }

  /**
   * Lance ensemble le lot Vinted et la file eBay des articles éligibles, puis ouvre le journal.
   * @param {number[]} articleIds - Articles à publier.
   * @param {Record<string, string>} journalQuery - Autres lots à suivre dans le même journal.
   * @returns {Promise<boolean>} Vrai si le journal a été ouvert.
   */
  async function publishOnVintedAndEbay(articleIds: number[], journalQuery: Record<string, string>): Promise<boolean> {
    const eligibleIds: number[] = eligibleIdsForVintedAndEbay(articleIds)
    if (!eligibleIds.length) {
      toast.add({
        title: 'Sélection invalide',
        description:
          'Pour les deux canaux : articles non vendus, avec photos (Vinted) et au moins une image HTTPS pour eBay, sans annonce eBay déjà créée.',
        color: 'warning',
      })
      return false
    }
    if (!canUseDesktopWorkers.value) {
      toast.add({
        title: 'Ouvrez GoupixDex sur votre PC',
        description:
          'Vinted s’exécute sur votre PC : lancez GoupixDex sur votre ordinateur, ou publiez seulement sur eBay.',
        color: 'warning',
      })
      return false
    }
    if (eligibleIds.length < articleIds.length) {
      toast.add({
        title: 'Certains articles sont ignorés',
        description: 'Seuls les articles éligibles pour eBay et Vinted sont inclus.',
        color: 'warning',
      })
    }
    isPublishingInBulk.value = true
    try {
      const [vintedStart, ebayStart] = await Promise.allSettled([
        startVintedBatch(eligibleIds),
        startEbayBatch(eligibleIds),
      ])

      if (vintedStart.status === 'fulfilled' && vintedStart.value.job_id) {
        if (ebayStart.status === 'fulfilled') {
          toast.add({
            title: 'Lots lancés',
            description: `Vinted : suivi du lot. eBay : ${ebayStart.value.queued} article(s) en file (API).`,
            color: 'success',
          })
        } else {
          toast.add({
            title: 'Lot Vinted lancé',
            description: `eBay : ${apiErrorMessage(ebayStart.reason)}`,
            color: 'warning',
          })
        }
        await navigateTo({ path: '/articles/listing-logs', query: { job: vintedStart.value.job_id, ...journalQuery } })
        await onPublicationsLaunched?.()
        return true
      }

      if (ebayStart.status === 'fulfilled') {
        toast.add({
          title: 'Lot eBay lancé',
          description:
            vintedStart.status === 'rejected'
              ? `Vinted : ${apiErrorMessage(vintedStart.reason)}`
              : `${ebayStart.value.queued} article(s) en file.`,
          color: vintedStart.status === 'rejected' ? 'warning' : 'success',
        })
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(eligibleIds[0]), ...journalQuery },
        })
        await onPublicationsLaunched?.()
        return true
      }

      const failures: string[] = []
      if (vintedStart.status === 'rejected') {
        failures.push(`Vinted : ${apiErrorMessage(vintedStart.reason)}`)
      }
      if (ebayStart.status === 'rejected') {
        failures.push(`eBay : ${apiErrorMessage(ebayStart.reason)}`)
      }
      toast.add({
        title: 'Impossible de lancer les lots',
        description: failures.length ? failures.join(' · ') : 'Erreur inconnue',
        color: 'error',
      })
    } finally {
      isPublishingInBulk.value = false
    }
    return false
  }

  /**
   * Lance sur le PC le lot Leboncoin des articles éligibles, publiés l’un après l’autre.
   * @param {number[]} articleIds - Articles à publier.
   * @returns {Promise<string | null>} L’identifiant du lot, ou null s’il n’a pas démarré (raison annoncée par un toast).
   */
  async function startLeboncoinPublication(articleIds: number[]): Promise<string | null> {
    if (!(await ensureLeboncoinPublishReady())) {
      return null
    }
    const eligibleIds: number[] = articleIds.filter((articleId: number): boolean => {
      const article: Article | undefined = findArticle(articleId)
      return Boolean(article && !article.is_sold && article.images?.length && !article.published_on_leboncoin)
    })
    if (!eligibleIds.length) {
      toast.add({
        title: 'Sélection invalide',
        description: 'Leboncoin : articles non vendus, pas déjà en ligne, avec au moins une photo.',
        color: 'warning',
      })
      return null
    }
    if (!canUseDesktopWorkers.value) {
      notifyPcUnreachable('La publication Leboncoin')
      return null
    }
    try {
      const { job_id } = await startLeboncoinBatch(eligibleIds)
      return job_id
    } catch (error: unknown) {
      toast.add({ title: 'Publication Leboncoin impossible', description: apiErrorMessage(error), color: 'error' })
      return null
    }
  }

  /**
   * Publie les articles sur chaque marketplace choisie, tous ensemble, puis ouvre le journal qui suit chaque lot.
   * @param {number[]} articleIds - Articles à publier.
   * @param {Marketplace[]} marketplaces - Marketplaces choisies.
   * @returns {Promise<void>} Résolue une fois le journal ouvert, ou les échecs annoncés.
   */
  async function publishArticlesInBulk(articleIds: number[], marketplaces: Marketplace[]): Promise<void> {
    const journalQuery: Record<string, string> = {}
    if (marketplaces.includes('leboncoin')) {
      const leboncoinJobId: string | null = await startLeboncoinPublication(articleIds)
      if (leboncoinJobId) {
        journalQuery.leboncoin_job = leboncoinJobId
      }
    }
    const isPublishingOnVinted: boolean = marketplaces.includes('vinted')
    const isPublishingOnEbay: boolean = marketplaces.includes('ebay')
    let hasOpenedJournal: boolean = false
    if (isPublishingOnVinted && isPublishingOnEbay) {
      hasOpenedJournal = await publishOnVintedAndEbay(articleIds, journalQuery)
    } else if (isPublishingOnVinted) {
      hasOpenedJournal = await publishOnVinted(articleIds, journalQuery)
    } else if (isPublishingOnEbay) {
      hasOpenedJournal = await publishOnEbay(articleIds, journalQuery)
    }
    if (!hasOpenedJournal && journalQuery.leboncoin_job) {
      await navigateTo({ path: '/articles/listing-logs', query: journalQuery })
    }
  }

  return { isPublishingInBulk, publishArticlesInBulk }
}
