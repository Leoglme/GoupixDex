<template>
  <UDashboardPanel id="market">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Vente
          </span>
        </template>
        <template #right>
          <UButton to="/articles/create" color="primary" variant="soft" icon="i-lucide-plus"> Nouvel article </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-4 px-3 py-3 sm:px-4 sm:py-4">
        <GoupixDexPageHeader
          title="Marché eBay"
          description="Estimez une carte ou un produit scellé : annonces actives et prix min / médian / moyen / max sur eBay France."
        />

        <GoupixDexPageTabs :items="MARKET_PAGE_TABS" />

        <!-- Formulaire de recherche -->
        <UCard>
          <template #header>
            <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <p class="text-highlighted font-medium">Paramètres de recherche</p>
              <p class="text-muted max-w-xs text-xs">
                La recherche est lancée à chaque soumission (aucun historique, aucun cache).
              </p>
            </div>
          </template>

          <GoupixDexMarketSearchForm
            :seed="marketSeed"
            :loading="loading"
            :result-count="result?.items?.length ?? null"
            @submit="onSubmit"
          />
        </UCard>

        <!-- Erreur -->
        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Recherche impossible"
          :description="error"
        />

        <!-- Résultats -->
        <template v-if="result">
          <GoupixDexMarketPriceStats
            :stats="result.stats"
            :total-matches="result.total_matches"
            :period-days="result.period_days"
            :outliers-excluded="result.outliers_excluded"
            :effective-query="result.effective_query"
          />

          <UAlert
            v-if="result.warnings?.length"
            color="warning"
            variant="subtle"
            icon="i-lucide-info"
            title="Remarques eBay"
          >
            <template #description>
              <ul class="list-disc space-y-0.5 pl-4 text-sm">
                <li v-for="(w, i) in result.warnings" :key="i">{{ w }}</li>
              </ul>
            </template>
          </UAlert>

          <section v-if="result.items.length" class="space-y-3">
            <div class="flex flex-wrap items-end justify-between gap-2">
              <div>
                <p class="text-highlighted text-sm font-medium">Annonces récentes</p>
                <p class="text-muted text-xs">
                  Cliquez sur « Créer article » pour préremplir le formulaire à partir d'une annonce.
                </p>
              </div>
            </div>

            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <GoupixDexMarketListingCard
                v-for="listing in result.items"
                :key="listing.item_id"
                :listing="listing"
                @create-article="onCreateArticle"
              />
            </div>
          </section>

          <UAlert
            v-else
            color="info"
            variant="subtle"
            icon="i-lucide-search-x"
            title="Aucun résultat pour cette recherche"
            description="Essayez d'élargir la période, retirer le filtre « France uniquement » ou reformuler votre requête."
          />

          <section v-if="result.outliers?.length" class="space-y-3">
            <details class="group border-default/60 bg-elevated/20 rounded-xl border border-dashed p-4">
              <summary class="text-muted flex cursor-pointer items-center justify-between gap-2 text-sm">
                <span class="inline-flex items-center gap-2">
                  <UIcon name="i-lucide-filter-x" class="size-4 text-amber-500" />
                  <span class="text-highlighted font-medium">
                    {{ result.outliers.length }} annonce<span v-if="result.outliers.length > 1">s</span> exclue<span
                      v-if="result.outliers.length > 1"
                      >s</span
                    >
                    du calcul (prix hors-marché)
                  </span>
                </span>
                <span class="text-muted text-xs transition group-open:rotate-180">
                  <UIcon name="i-lucide-chevron-down" class="size-4" />
                </span>
              </summary>
              <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                <GoupixDexMarketListingCard
                  v-for="listing in result.outliers"
                  :key="listing.item_id"
                  :listing="listing"
                  @create-article="onCreateArticle"
                />
              </div>
            </details>
          </section>
        </template>

        <!-- État initial -->
        <div
          v-else-if="!loading"
          class="border-default/60 bg-elevated/20 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
        >
          <UIcon name="i-lucide-sparkles" class="text-primary size-8" />
          <p class="text-highlighted text-sm font-medium">Tapez votre recherche pour démarrer</p>
          <p class="text-muted max-w-md text-xs">
            Exemple : <span class="font-medium">« Prismatic Evolutions Elite Trainer Box FR »</span>,
            <span class="font-medium">« Pikachu VMAX PSA 10 »</span> ou
            <span class="font-medium">« Charizard 4/102 »</span>.
          </p>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { MarketListing, MarketSearchInput } from '~/composables/useMarketSearch'
import { buildArticlePrefillFromListing } from '~/composables/useMarketListingPrefill'
import { parseMarketSearchFromQuery } from '~/utils/marketSearchQuery'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Marché eBay — Annonces en cours',
  'Analysez en direct les prix des cartes Pokémon et produits scellés sur eBay France : prix minimum, moyen, médian et maximum des annonces actives.',
)

const route = useRoute()
const { loading, error, result, search } = useMarketSearch()
const toast = useToast()
const lastQuery = ref<string | null>(null)

const marketSeed = computed(() => parseMarketSearchFromQuery(route.query))

/**
 * Exécute la recherche marché + toast si aucun résultat.
 * @param input - Paramètres (formulaire ou query string)
 * @returns {Promise<void>} Résultat API dans `result`
 */
async function runMarketSearch(input: MarketSearchInput): Promise<void> {
  lastQuery.value = input.q
  const res = await search(input)
  if (res && res.items.length === 0) {
    toast.add({
      title: 'Aucune annonce trouvée',
      description: "Essayez d'élargir la période, retirer le filtre « France uniquement » ou reformuler la recherche.",
      color: 'warning',
    })
  }
}

/**
 * Soumission du formulaire.
 * @param input - Search form payload
 * @returns {Promise<void>} Résout quand la requête finit
 */
async function onSubmit(input: MarketSearchInput): Promise<void> {
  await runMarketSearch(input)
}

if (import.meta.client) {
  watch(
    () => route.fullPath,
    async () => {
      if (route.name !== 'market') {
        return
      }
      if (route.query.auto !== '1') {
        return
      }
      const input = parseMarketSearchFromQuery(route.query)
      if (!input) {
        return
      }
      await runMarketSearch(input)
    },
    { immediate: true },
  )
}

/**
 * Navigate to article creation with query params prefilled from the listing.
 * @param listing - Selected marketplace row
 * @returns {Promise<void>} Resolves after navigation is triggered
 */
async function onCreateArticle(listing: MarketListing): Promise<void> {
  const payload = buildArticlePrefillFromListing(listing)
  await navigateTo({ path: '/articles/create', query: payload })
}
</script>
