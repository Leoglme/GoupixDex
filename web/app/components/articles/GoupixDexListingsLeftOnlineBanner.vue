<template>
  <div
    v-if="listingsLeftOnlineCount"
    class="app-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
    role="status"
  >
    <div class="flex min-w-0 items-center gap-3">
      <span class="app-icon-tile" aria-hidden="true">
        <UIcon name="i-lucide-store" class="size-5 text-(--app-accent)" />
      </span>
      <div class="min-w-0 space-y-0.5">
        <p class="text-highlighted text-sm font-semibold">{{ bannerTitle }}</p>
        <p class="text-muted line-clamp-2 text-xs leading-relaxed">{{ listingsLeftOnlineSummary }}</p>
      </div>
    </div>
    <UButton
      icon="i-lucide-trash-2"
      size="sm"
      class="shrink-0 self-start sm:self-auto"
      :loading="isStartingRemoval"
      @click="onRemoveClick"
    >
      Retirer
    </UButton>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { Marketplace } from '~/types/Marketplace'
import { apiErrorMessage } from '~/composables/useApiError'
import { marketplaceNamesLabel } from '~/utils/marketplaces'

const toast = useToast()
const { fetchArticlesWithListingsLeftOnline, removeEveryListingLeftOnline } = useSoldArticleListingsRemoval()
const { articleMutationCounter } = useGoupixDrawerStack()
const { confirm: confirmAction } = useGoupixConfirm()

const articlesWithListingsLeftOnline: Ref<Article[]> = ref([])
const isStartingRemoval: Ref<boolean> = ref(false)

const vintedArticles: ComputedRef<Article[]> = computed((): Article[] =>
  articlesWithListingsLeftOnline.value.filter((article: Article): boolean => Boolean(article.pending_vinted_unlist)),
)

const leboncoinArticles: ComputedRef<Article[]> = computed((): Article[] =>
  articlesWithListingsLeftOnline.value.filter((article: Article): boolean => Boolean(article.pending_leboncoin_unlist)),
)

const listingsLeftOnlineCount: ComputedRef<number> = computed(
  (): number => vintedArticles.value.length + leboncoinArticles.value.length,
)

const marketplacesWithListingsLeftOnline: ComputedRef<Marketplace[]> = computed((): Marketplace[] => {
  const marketplaces: Marketplace[] = []
  if (vintedArticles.value.length) {
    marketplaces.push('vinted')
  }
  if (leboncoinArticles.value.length) {
    marketplaces.push('leboncoin')
  }
  return marketplaces
})

const bannerTitle: ComputedRef<string> = computed((): string =>
  listingsLeftOnlineCount.value > 1
    ? `${listingsLeftOnlineCount.value} annonces encore en ligne après une vente`
    : '1 annonce encore en ligne après une vente',
)

const listingsLeftOnlineSummary: ComputedRef<string> = computed((): string =>
  [
    ...(vintedArticles.value.length ? [`Vinted : ${joinCardNames(vintedArticles.value)}`] : []),
    ...(leboncoinArticles.value.length ? [`Leboncoin : ${joinCardNames(leboncoinArticles.value)}`] : []),
  ].join(' · '),
)

/**
 * Joint les noms des cartes de ces articles pour une phrase.
 * @param {Article[]} articles - Articles vendus à nommer.
 * @returns {string} Le nom du Pokémon de chaque article, à défaut son titre, séparés par des virgules.
 */
function joinCardNames(articles: Article[]): string {
  return articles.map((article: Article): string => article.pokemon_name || article.title).join(', ')
}

/**
 * Relit les articles vendus dont une annonce est encore en ligne ; une erreur de lecture garde le dernier état connu.
 * @returns {Promise<void>} Résolue une fois la liste à jour.
 */
async function loadArticlesWithListingsLeftOnline(): Promise<void> {
  articlesWithListingsLeftOnline.value = await fetchArticlesWithListingsLeftOnline().catch(
    (): Article[] => articlesWithListingsLeftOnline.value,
  )
}

/**
 * Demande confirmation puis fait retirer par le PC toutes les annonces restées en ligne.
 * @returns {Promise<void>} Résolue une fois les retraits lancés, ou la confirmation refusée.
 */
async function onRemoveClick(): Promise<void> {
  const shouldRemove: boolean = await confirmAction({
    title: 'Retirer les annonces restées en ligne ?',
    body: `Chrome va s’ouvrir sur votre PC pour supprimer ces annonces sur ${marketplaceNamesLabel(marketplacesWithListingsLeftOnline.value)}.`,
    confirmLabel: 'Retirer',
    confirmColor: 'error',
  })
  if (!shouldRemove) {
    return
  }

  isStartingRemoval.value = true
  try {
    await removeEveryListingLeftOnline(articlesWithListingsLeftOnline.value)
  } catch (error: unknown) {
    toast.add({ title: 'Retrait impossible', description: apiErrorMessage(error), color: 'error' })
  } finally {
    isStartingRemoval.value = false
  }
}

watch(articleMutationCounter, (): void => {
  loadArticlesWithListingsLeftOnline()
})

onMounted((): void => {
  loadArticlesWithListingsLeftOnline()
})
</script>
