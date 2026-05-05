<template>
  <UDashboardPanel id="vendus-ebay">
    <template #header>
      <UDashboardNavbar title="Vendus eBay">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/market" color="neutral" variant="soft" icon="i-lucide-trending-up"> Prix du marché </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-6 px-4 py-6 sm:space-y-8 sm:px-6 sm:py-8">
        <!-- Bandeau contexte -->
        <div
          class="border-default from-primary/10 via-elevated/60 to-primary/5 relative overflow-hidden rounded-2xl border bg-gradient-to-br px-5 py-5 sm:px-7 sm:py-7"
        >
          <div class="bg-primary/10 pointer-events-none absolute -top-16 -right-16 size-48 rounded-full blur-3xl" />
          <div class="bg-primary/5 pointer-events-none absolute -bottom-24 -left-10 size-44 rounded-full blur-3xl" />
          <div class="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="max-w-2xl space-y-2">
              <p class="text-primary text-xs font-medium tracking-wide uppercase">Ventes terminées · eBay France</p>
              <h1 class="text-highlighted text-xl font-semibold tracking-tight sm:text-2xl">
                Cartes et lots récemment vendus sur eBay France
              </h1>
              <p class="text-muted text-sm leading-relaxed sm:text-base">
                GoupixDex parse la page publique « vendus » d'eBay pour remonter les annonces clôturées, avec leur prix
                de transaction et la date de vente. Aucun scope développeur eBay requis.
              </p>
            </div>
            <div
              class="bg-primary/15 text-primary hidden size-24 shrink-0 items-center justify-center rounded-2xl lg:flex"
            >
              <UIcon name="i-lucide-circle-check" class="size-12" />
            </div>
          </div>
        </div>

        <!-- Formulaire de recherche -->
        <UCard class="ring-default/60 shadow-sm ring-1">
          <template #header>
            <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <p class="text-highlighted font-medium">Paramètres de recherche</p>
              <p class="text-muted max-w-xs text-xs">
                La recherche est lancée à chaque soumission (aucun historique, aucun cache).
              </p>
            </div>
          </template>

          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-4 md:flex-row md:items-end">
              <UFormField label="Recherche" class="min-w-0 flex-1" required>
                <UInput
                  v-model="q"
                  icon="i-lucide-search"
                  placeholder="ex. carte pokemon, Pikachu VMAX…"
                  class="w-full"
                  @keyup.enter="onSearchEnter"
                />
              </UFormField>
              <UFormField label="Fenêtre (vente)" class="w-full md:w-72">
                <USelect v-model="windowKey" :items="windowOptions" value-key="value" label-key="label" class="w-full" />
              </UFormField>
              <UButton
                type="button"
                color="primary"
                :disabled="q.trim().length < 2"
                class="shrink-0"
                @click.prevent.stop="runLoad"
              >
                <span class="inline-flex items-center gap-2">
                  <UIcon v-if="loading" name="i-lucide-loader-circle" class="size-4 animate-spin" />
                  {{ loading ? 'Recherche…' : 'Rechercher' }}
                </span>
              </UButton>
            </div>

            <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <UTabs
                v-model="viewMode"
                :items="viewModeTabs"
                size="sm"
                color="primary"
                variant="link"
                class="w-full sm:w-auto"
              />
              <p v-if="viewMode !== 'list'" class="text-muted text-xs">
                {{ topModeHint }}
              </p>
            </div>
          </div>
        </UCard>

        <!-- Lien manuel -->
        <div class="flex flex-wrap gap-2">
          <UButton
            :to="manualUrl"
            target="_blank"
            rel="noopener"
            color="neutral"
            variant="soft"
            icon="i-lucide-external-link"
          >
            Ouvrir la même recherche « vendus » sur eBay.fr
          </UButton>
        </div>

        <!-- Erreur -->
        <UAlert
          v-if="displayError"
          color="warning"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Récupération limitée"
          :description="displayError"
        />

        <!-- Résultats : liste -->
        <template v-else-if="viewMode === 'list'">
          <template v-if="hasSearched && listRows.length">
            <p class="text-muted text-sm">
              {{ listRows.length }} vente(s) dans la fenêtre. Tri d'origine eBay : terminées récemment.
            </p>
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <GoupixDexEbaySoldCard
                v-for="(row, idx) in listRows"
                :key="row.item_id || `${idx}-${row.title.slice(0, 20)}`"
                :row="row"
              />
            </div>
          </template>

          <UAlert
            v-else-if="hasSearched && listResult && !listRows.length && !loading"
            color="info"
            variant="subtle"
            icon="i-lucide-search-x"
            title="Aucune vente dans cette fenêtre"
            description="Essayez d'élargir à 7 jours ou reformulez la recherche."
          />

          <div v-else-if="loading" class="flex justify-center py-16">
            <UIcon name="i-lucide-loader-circle" class="text-primary size-10 animate-spin" />
          </div>

          <div
            v-else-if="!hasSearched"
            class="border-default/60 bg-elevated/20 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
          >
            <UIcon name="i-lucide-sparkles" class="text-primary size-8" />
            <p class="text-highlighted text-sm font-medium">Tapez votre recherche pour démarrer</p>
            <p class="text-muted max-w-md text-xs">
              Exemple : <span class="font-medium">« Prismatic Evolutions ETB »</span>,
              <span class="font-medium">« Pikachu VMAX PSA 10 »</span> ou
              <span class="font-medium">« Charizard 4/102 »</span>.
            </p>
          </div>
        </template>

        <!-- Résultats : tops (cards / graded / sealed) -->
        <template v-else>
          <template v-if="hasSearched && currentTopRows.length">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="text-muted text-sm">
                Top {{ currentTopRows.length }} {{ currentTopLabel }} — agrégés sur
                {{ topResult?.total_observed ?? 0 }} ventes scrapées.
              </p>
              <div class="text-muted flex flex-wrap items-center gap-3 text-xs">
                <span class="inline-flex items-center gap-1">
                  <UIcon name="i-lucide-layers" class="size-3.5" />
                  {{ topResult?.groups_count.cards ?? 0 }} cartes
                </span>
                <span class="inline-flex items-center gap-1">
                  <UIcon name="i-lucide-shield-check" class="size-3.5" />
                  {{ topResult?.groups_count.graded ?? 0 }} gradées
                </span>
                <span class="inline-flex items-center gap-1">
                  <UIcon name="i-lucide-package" class="size-3.5" />
                  {{ topResult?.groups_count.sealed ?? 0 }} scellés
                </span>
              </div>
            </div>
            <div class="space-y-3">
              <GoupixDexEbaySoldTopRow
                v-for="row in currentTopRows"
                :key="`${row.category}-${row.fingerprint}-${row.grade ?? 'raw'}`"
                :row="row"
              />
            </div>
          </template>

          <UAlert
            v-else-if="hasSearched && topResult && !currentTopRows.length && !loading"
            color="info"
            variant="subtle"
            icon="i-lucide-search-x"
            :title="emptyTitle"
            :description="emptyDescription"
          />

          <div v-else-if="loading" class="flex justify-center py-16">
            <UIcon name="i-lucide-loader-circle" class="text-primary size-10 animate-spin" />
          </div>

          <div
            v-else-if="!hasSearched"
            class="border-default/60 bg-elevated/20 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
          >
            <UIcon :name="emptyIcon" class="text-primary size-8" />
            <p class="text-highlighted text-sm font-medium">Lancez une recherche pour générer le top</p>
            <p class="text-muted max-w-md text-xs">
              Le top fonctionne mieux avec des requêtes larges :
              <span class="font-medium">« carte pokemon »</span>,
              <span class="font-medium">« pokemon TCG »</span>,
              <span class="font-medium">« Charizard »</span>.
            </p>
          </div>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { TabsItem } from '@nuxt/ui'

import type { EbaySoldScrapeRow } from '~/composables/useEbaySoldScrape'
import type { EbaySoldTopRow } from '~/composables/useEbaySoldTop'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Vendus eBay',
  'Ventes terminées Pokémon TCG sur eBay France (page publique, sans scope Marketplace Insights).',
)

type ViewMode = 'list' | 'top-cards' | 'top-graded' | 'top-sealed'
type WindowKey = '24h' | '7d' | '30d'

const windowOptions = [
  { label: 'Dernières 24 heures', value: '24h' as const },
  { label: '7 derniers jours', value: '7d' as const },
  { label: '30 derniers jours', value: '30d' as const }
]

const WINDOW_HOURS: Record<WindowKey, number> = {
  '24h': 24,
  '7d': 168,
  '30d': 720
}

const viewModeTabs: TabsItem[] = [
  { label: 'Liste des ventes', value: 'list', icon: 'i-lucide-list' },
  { label: 'Top cartes', value: 'top-cards', icon: 'i-lucide-layers' },
  { label: 'Top gradées', value: 'top-graded', icon: 'i-lucide-shield-check' },
  { label: 'Top scellés', value: 'top-sealed', icon: 'i-lucide-package' }
]

const q = ref('carte pokemon')
const windowKey = ref<WindowKey>('7d')
const viewMode = ref<ViewMode>('list')
/** True after the first explicit search — no auto-fetch on mount. */
const hasSearched = ref(false)

const windowHoursNum = computed(() => WINDOW_HOURS[windowKey.value])

const listScrape = useEbaySoldScrape()
const topScrape = useEbaySoldTop()

const listResult = listScrape.result
const topResult = topScrape.result

const listRows = computed<EbaySoldScrapeRow[]>(() => listResult.value?.items ?? [])

const currentTopRows = computed<EbaySoldTopRow[]>(() => {
  const r = topResult.value
  if (!r) {
    return []
  }
  if (viewMode.value === 'top-graded') {
    return r.graded
  }
  if (viewMode.value === 'top-sealed') {
    return r.sealed
  }
  if (viewMode.value === 'top-cards') {
    return r.cards
  }
  return []
})

const currentTopLabel = computed(() => {
  if (viewMode.value === 'top-graded') {
    return 'cartes gradées'
  }
  if (viewMode.value === 'top-sealed') {
    return 'items scellés'
  }
  return 'cartes'
})

const topModeHint = computed(() => {
  if (viewMode.value === 'top-graded') {
    return 'Cartes notées PSA / BGS / CGC. Le grade fait partie de la clé de regroupement (PSA 10 ≠ PSA 9).'
  }
  if (viewMode.value === 'top-sealed') {
    return 'Produits scellés détectés (ETB, display, blister, tin, coffret, booster box…).'
  }
  return 'Cartes brutes (non gradées, hors produits scellés). Regroupées par numéro #/total + nom.'
})

const emptyTitle = computed(() => {
  if (viewMode.value === 'top-graded') {
    return 'Aucune carte gradée détectée'
  }
  if (viewMode.value === 'top-sealed') {
    return 'Aucun produit scellé détecté'
  }
  return 'Aucune carte raw à classer'
})

const emptyDescription = computed(() => {
  if (viewMode.value === 'top-graded') {
    return 'Essayez d\'ajouter « PSA », « BGS » ou « CGC » à votre recherche, ou élargissez la fenêtre à 7 jours.'
  }
  if (viewMode.value === 'top-sealed') {
    return 'Essayez « ETB », « display », « scellé » dans la recherche, ou élargissez la fenêtre à 7 jours.'
  }
  return 'Élargissez la fenêtre à 7 jours ou utilisez une recherche moins spécifique.'
})

const emptyIcon = computed(() => {
  if (viewMode.value === 'top-graded') {
    return 'i-lucide-shield-check'
  }
  if (viewMode.value === 'top-sealed') {
    return 'i-lucide-package'
  }
  return 'i-lucide-trophy'
})

const loading = computed(() => listScrape.loading.value || topScrape.loading.value)

const displayError = computed(() => {
  if (viewMode.value === 'list') {
    return listScrape.error.value ?? listResult.value?.error ?? ''
  }
  return topScrape.error.value ?? topResult.value?.error ?? ''
})

/** eBay « vendus » search URL — usable even if the API is unreachable. */
const manualUrl = computed(() => {
  const fromApi = (viewMode.value === 'list' ? listResult.value : topResult.value)?.ebay_sold_search_url?.trim()
  if (fromApi) {
    return fromApi
  }
  const kw = encodeURIComponent(q.value.trim())
  return `https://www.ebay.fr/sch/i.html?_nkw=${kw}&LH_Sold=1&LH_Complete=1&_sop=13&_ipg=50&rt=nc`
})

/**
 * Trigger a search when pressing Enter in the keyword input.
 *
 * @returns {void} Nothing.
 */
function onSearchEnter(): void {
  if (q.value.trim().length >= 2) {
    void runLoad()
  }
}

/**
 * Submit a sold-listings request matching the current view mode.
 * The 3 « top » modes share the same payload — switching between them
 * does not retrigger a fetch.
 *
 * @returns {Promise<void>} Resolves once the request finishes (success or error).
 */
async function runLoad(): Promise<void> {
  if (q.value.trim().length < 2) {
    return
  }
  hasSearched.value = true
  if (viewMode.value === 'list') {
    await listScrape.load({
      q: q.value,
      windowHours: windowHoursNum.value,
      limit: 50
    })
    return
  }
  await topScrape.load({
    q: q.value,
    windowHours: windowHoursNum.value,
    scrapeLimit: 180,
    topLimit: 50,
    minCount: 1
  })
}

watch(viewMode, (next, prev) => {
  if (!hasSearched.value || q.value.trim().length < 2) {
    return
  }
  const wasList = prev === 'list'
  const isList = next === 'list'
  // Switching between the 3 « top » sub-tabs reuses the same payload — no refetch.
  if (wasList === isList) {
    return
  }
  void runLoad()
})
</script>
