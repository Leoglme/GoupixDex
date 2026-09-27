<template>
  <UDashboardPanel :id="`article-edit-${id}`">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            {{ relistMode ? 'Remise en vente' : isReviewBeforePublishing ? 'Avant publication' : 'Modification' }}
          </span>
        </template>
        <template #right>
          <UButton :to="`/articles/${id}`" color="neutral" variant="ghost" icon="i-lucide-eye"> Fiche </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full">
        <GoupixDexBackLink to="/articles" />

        <div v-if="loading" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
        </div>

        <template v-else-if="article">
          <GoupixDexPageHeader
            v-if="isReviewBeforePublishing"
            title="Vérifier avant publication"
            :description="REVIEW_PAGE_DESCRIPTION"
          />
          <GoupixDexPageHeader
            v-else
            :title="relistMode ? 'Ajuster avant republication' : 'Modifier l’article'"
            :description="
              relistMode
                ? 'Vérifiez le prix avec les repères Cardmarket, puis enregistrez et publiez sur les canaux souhaités.'
                : 'Mettez à jour la fiche, les photos et les prix de votre annonce.'
            "
          />

          <div v-if="isReviewBeforePublishing" class="app-card flex items-center gap-3 p-4" role="status">
            <span class="app-icon-tile" aria-hidden="true">
              <UIcon name="i-lucide-send" class="size-5 text-(--app-accent)" />
            </span>
            <div class="min-w-0 space-y-0.5">
              <p class="text-highlighted text-sm font-semibold">
                Publication sur {{ marketplaceNamesLabel(reviewMarketplaces) }} après l’enregistrement
              </p>
              <p class="text-muted text-xs leading-relaxed">
                Rien n’est publié avant l’enregistrement.
                <span v-if="queuedArticleIds.length">
                  Encore {{ queuedArticleIds.length }} fiche{{ queuedArticleIds.length > 1 ? 's' : '' }} à vérifier
                  ensuite.
                </span>
              </p>
            </div>
          </div>

          <UAlert v-if="relistMode" color="primary" variant="subtle" icon="i-lucide-refresh-cw" title="Remise en vente">
            <template #description>
              <span class="text-sm leading-relaxed">
                Rien n’est publié tant que vous n’avez pas enregistré et lancé la mise en ligne.
                <span v-if="queuedArticleIds.length">
                  Encore {{ queuedArticleIds.length }} fiche{{ queuedArticleIds.length > 1 ? 's' : '' }} dans cette
                  série.
                </span>
              </span>
            </template>
          </UAlert>

          <UCard v-if="!relistMode && !isReviewBeforePublishing" class="ring-default ring-1">
            <div class="flex flex-wrap items-center gap-2 px-1 py-0.5">
              <span class="text-muted text-sm">Vinted</span>
              <UBadge :color="(article.published_on_vinted ?? false) ? 'success' : 'neutral'" variant="subtle">
                {{ (article.published_on_vinted ?? false) ? 'En ligne' : 'Non' }}
              </UBadge>
              <span class="text-muted text-sm">eBay</span>
              <UBadge :color="(article.published_on_ebay ?? false) ? 'success' : 'neutral'" variant="subtle">
                {{ (article.published_on_ebay ?? false) ? 'En ligne' : 'Non' }}
              </UBadge>
              <UButton
                v-if="!article.is_sold && !(article.published_on_ebay ?? false)"
                size="xs"
                variant="soft"
                color="primary"
                :loading="publishingEbay"
                icon="i-lucide-shopping-bag"
                @click="publishEbayOnly"
              >
                Publier sur eBay
              </UButton>
            </div>
          </UCard>

          <UCard class="ring-default ring-1">
            <GoupixDexArticleForm
              mode="edit"
              :article="article"
              :relist-mode="relistMode"
              :loading="submitting"
              :loading-hint="submitLoadingHint"
              :submit-label="isReviewBeforePublishing ? 'Enregistrer et publier' : undefined"
              @submit-edit="onSubmitEdit"
            />
          </UCard>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'
import type { Marketplace } from '~/types/Marketplace'
import { useArticleMarketplacePublication } from '~/composables/useArticleMarketplacePublication'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'
import {
  parseRelistQueueParam,
  publishReviewLocation,
  relistSuccessorLocation,
  RELIST_QUEUE_STORAGE_KEY,
} from '~/utils/articleRelistQueue'
import { internalPathOrFallback } from '~/utils/internalPath'
import { isPublishedOnMarketplace, marketplaceNamesLabel, parseMarketplaceList } from '~/utils/marketplaces'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const { getArticle, updateArticle, publishArticleToEbay, publishArticleToVinted } = useArticles()
const toast = useToast()
const { canUseDesktopWorkers } = useDesktopWorkers()
const { publishArticleOnMarketplaces } = useArticleMarketplacePublication()

const REVIEW_PAGE_DESCRIPTION: string =
  'Ajustez le prix avec les repères Cardmarket et complétez la fiche : l’enregistrement lance la mise en ligne.'

const article: Ref<Article | null> = ref(null)
const loading: Ref<boolean> = ref(true)
const submitting: Ref<boolean> = ref(false)
const publishingEbay: Ref<boolean> = ref(false)
const vintedSubmit: Ref<boolean> = ref(false)
const isPublishingReviewedArticle: Ref<boolean> = ref(false)

const id: ComputedRef<number> = computed(() => Number(route.params.id))

const relistMode: ComputedRef<boolean> = computed(() => route.query.relist === '1')

const queuedArticleIds: ComputedRef<number[]> = computed(() => parseRelistQueueParam(route.query.queue))

const isReviewBeforePublishing: ComputedRef<boolean> = computed((): boolean => route.query.review === '1')

const reviewMarketplaces: ComputedRef<Marketplace[]> = computed((): Marketplace[] =>
  parseMarketplaceList(route.query.publish),
)

const submitLoadingHint: ComputedRef<string | undefined> = computed((): string | undefined => {
  if (isPublishingReviewedArticle.value) {
    return `Publication sur ${marketplaceNamesLabel(reviewMarketplaces.value)} en cours…`
  }
  return submitting.value && vintedSubmit.value ? 'Enregistrement… puis journal Vinted.' : undefined
})

async function load(): Promise<void> {
  loading.value = true
  try {
    article.value = await getArticle(id.value)
  } catch (e) {
    toast.add({ title: 'Article introuvable', description: apiErrorMessage(e), color: 'error' })
    await navigateTo('/articles')
  } finally {
    loading.value = false
  }
}

async function advanceRelistQueueOrArticles(): Promise<void> {
  const next = relistSuccessorLocation(queuedArticleIds.value)
  if (next) {
    toast.add({
      title: 'Article enregistré',
      description: 'Passez à la fiche suivante de la série.',
      color: 'success',
    })
    await navigateTo(next)
    return
  }
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(RELIST_QUEUE_STORAGE_KEY)
  }
  toast.add({
    title: 'Série terminée',
    description: 'Toutes les fiches de la remise en vente sont traitées.',
    color: 'success',
  })
  await navigateTo('/articles')
}

async function publishEbayOnly(): Promise<void> {
  publishingEbay.value = true
  try {
    const { ebay } = await publishArticleToEbay(id.value)
    if (ebay?.status === 'running' && ebay?.stream_path) {
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(id.value) },
      })
      return
    }
    toast.add({
      title: 'Publication eBay démarrée',
      description: 'Traitement en arrière-plan — rafraîchissez la liste dans quelques instants.',
      color: 'success',
    })
    await load()
  } catch (e) {
    toast.add({ title: 'eBay', description: apiErrorMessage(e), color: 'error' })
  } finally {
    publishingEbay.value = false
  }
}

/**
 * Enregistre la fiche vérifiée, la publie sur les marketplaces choisies et attend la fin, puis ouvre la fiche suivante ou revient à la page de départ.
 * @param {ArticleUpdateBody} body - Modifications de la fiche.
 * @returns {Promise<void>} Résolue après la navigation, ou l'erreur annoncée.
 */
async function saveAndPublishReviewedArticle(body: ArticleUpdateBody): Promise<void> {
  submitting.value = true
  try {
    const updatedArticle: Article = await updateArticle(id.value, body)
    article.value = updatedArticle
    isPublishingReviewedArticle.value = true
    await publishArticleOnMarketplaces(
      updatedArticle,
      reviewMarketplaces.value.filter(
        (marketplace: Marketplace): boolean => !isPublishedOnMarketplace(updatedArticle, marketplace),
      ),
    )
    const [nextArticleId, ...laterArticleIds]: number[] = queuedArticleIds.value
    const returnPath: string = internalPathOrFallback(route.query.back, '/articles')
    if (nextArticleId !== undefined) {
      await navigateTo(publishReviewLocation(nextArticleId, laterArticleIds, reviewMarketplaces.value, returnPath))
      return
    }
    await navigateTo(returnPath)
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    isPublishingReviewedArticle.value = false
    submitting.value = false
  }
}

/**
 * Enregistre la fiche, puis selon la page la publie avant la suivante (vérification, remise en vente) ou revient à la liste.
 * @param {ArticleUpdateBody} body - Modifications de la fiche.
 * @param {{ publishVinted: boolean; publishEbay: boolean }} [relist] - Canaux cochés en remise en vente.
 * @returns {Promise<void>} Résolue après la navigation, ou l'erreur annoncée.
 */
async function onSubmitEdit(
  body: ArticleUpdateBody,
  relist?: { publishVinted: boolean; publishEbay: boolean },
): Promise<void> {
  if (isReviewBeforePublishing.value) {
    await saveAndPublishReviewedArticle(body)
    return
  }
  vintedSubmit.value = Boolean(relist?.publishVinted)
  submitting.value = true
  try {
    const updated = await updateArticle(id.value, body)
    article.value = updated

    if (!relistMode.value || !relist) {
      toast.add({ title: 'Article mis à jour', color: 'success' })
      await navigateTo('/articles')
      return
    }

    const relistQuery: Record<string, string> = { relist: '1' }
    const queueStr = typeof route.query.queue === 'string' && route.query.queue.trim() ? route.query.queue.trim() : ''
    if (queueStr) {
      relistQuery.queue = queueStr
    }

    if (relist.publishVinted && canUseDesktopWorkers.value) {
      try {
        await publishArticleToVinted(id.value)
      } catch (err) {
        toast.add({
          title: 'Worker Vinted local',
          description: apiErrorMessage(err),
          color: 'error',
        })
        await advanceRelistQueueOrArticles()
        return
      }
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(id.value), progress: 'local', ...relistQuery },
      })
      return
    }

    if (relist.publishEbay) {
      const { ebay } = await publishArticleToEbay(id.value)
      if (ebay?.status === 'running' && ebay?.stream_path) {
        await navigateTo({
          path: '/articles/listing-logs',
          query: { article: String(id.value), ...relistQuery },
        })
        return
      }
    }

    if (relist.publishVinted && !canUseDesktopWorkers.value) {
      toast.add({
        title: 'Vinted non lancé',
        description: 'Ouvrez GoupixDex sur votre PC pour publier sur Vinted.',
        color: 'warning',
      })
    }

    await advanceRelistQueueOrArticles()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    submitting.value = false
  }
}

function articleTitleForSeo(a: Article): string {
  const t = a.title
  return t.length > 42 ? `${t.slice(0, 39)}…` : t
}

useSeoMeta({
  title: computed(() => {
    if (!article.value) {
      return 'Article · GoupixDex'
    }
    const suffix = relistMode.value
      ? 'remise en vente'
      : isReviewBeforePublishing.value
        ? 'avant publication'
        : 'modification'
    return `${articleTitleForSeo(article.value)} — ${suffix} · GoupixDex`
  }),
  description: computed(() => {
    if (!article.value) {
      return 'Modifiez une fiche carte ou annonce dans GoupixDex.'
    }
    return `Éditez « ${article.value.title} » : prix, repères Cardmarket, photos et publication marketplace.`
  }),
})

watch(
  () => route.params.id,
  () => {
    void load()
  },
)

onMounted((): void => {
  void load()
})
</script>
