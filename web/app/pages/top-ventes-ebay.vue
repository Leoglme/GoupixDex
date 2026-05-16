<template>
  <UDashboardPanel id="vendus-ebay">
    <template #header>
      <UDashboardNavbar title="Ventes terminées eBay">
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
                Explorez les ventes récentes correspondant à votre recherche : dernier prix affiché et période au choix
                (24 h à 30 jours), puis comparez aussi les tops les plus fréquents.
              </p>
            </div>
            <div
              class="bg-primary/15 hidden size-24 shrink-0 items-center justify-center rounded-2xl text-[#E53238] lg:flex"
            >
              <UIcon name="i-simple-icons-ebay" class="size-12" />
            </div>
          </div>
        </div>

        <!-- Formulaire de recherche -->
        <UCard class="ring-default/60 shadow-sm ring-1">
          <template #header>
            <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <p class="text-highlighted font-medium">Paramètres de recherche</p>
              <p class="text-muted max-w-sm text-xs sm:text-end">
                Même recherche et même fenêtre : résultat immédiat si disponible (voir indicateur sous les résultats).
              </p>
            </div>
          </template>

          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-end">
              <UFormField label="Recherche" class="min-w-0 flex-1" required>
                <UInput
                  v-model="q"
                  icon="i-lucide-search"
                  placeholder="ex. carte pokemon, Pikachu VMAX…"
                  class="w-full"
                  @keyup.enter="onSearchEnter"
                />
              </UFormField>
              <UFormField label="Fenêtre (vente)" class="w-full lg:w-56">
                <USelect
                  v-model="windowKey"
                  :items="windowOptions"
                  value-key="value"
                  label-key="label"
                  class="w-full"
                />
              </UFormField>
              <UFormField label="Langue (item)" class="w-full lg:w-52">
                <USelect
                  v-model="languageKey"
                  :items="languageOptions"
                  value-key="value"
                  label-key="label"
                  class="w-full"
                />
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

        <!-- Global progress bar (one eBay analysis feeds list + tops) -->
        <div v-if="loading" class="border-default bg-elevated/30 flex flex-col gap-2 rounded-xl border p-4">
          <div class="flex items-center justify-between gap-3">
            <span class="text-highlighted inline-flex items-center gap-2 text-sm font-medium">
              <UIcon name="i-lucide-loader-circle" class="text-primary size-4 animate-spin" />
              {{ progressLabel }}
            </span>
            <span class="text-muted text-xs tabular-nums">{{ progressPercent }}%</span>
          </div>
          <UProgress :model-value="progressPercent" :max="100" size="sm" color="primary" />
          <p class="text-muted text-xs">
            {{ totalObservedSoFar }} vente(s) analysée(s) · {{ streamingListRows.length }} dans la fenêtre ·
            regroupement au terme de l’analyse.
          </p>
        </div>

        <!-- Live streaming preview (list view only) — replaced by final list when complete -->
        <template v-if="!displayError && viewMode === 'list' && loading && streamingListRows.length">
          <p class="text-muted text-xs">
            Aperçu en direct — la liste finale remplace cet aperçu à la fin de l’analyse.
          </p>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <GoupixDexEbaySoldCard
              v-for="(row, idx) in streamingListRows"
              :key="`stream-${row.item_id || idx}-${row.title.slice(0, 20)}`"
              :row="row"
            />
          </div>
        </template>

        <!-- List results -->
        <template v-if="!displayError && viewMode === 'list'">
          <template v-if="hasSearched && listRows.length">
            <p class="text-muted text-sm">
              {{ listRows.length }} vente(s) dans la fenêtre. Tri d'origine eBay : terminées récemment.
              <span v-if="topScrape.cached.value" class="text-primary inline-flex items-center gap-1 font-medium">
                · <UIcon name="i-lucide-zap" class="size-3.5" /> servi depuis le cache
              </span>
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
            v-else-if="hasSearched && topResult && !listRows.length && !loading"
            color="info"
            variant="subtle"
            icon="i-lucide-search-x"
            title="Aucune vente dans cette fenêtre"
            description="Essayez d'élargir à 7 jours ou reformulez la recherche."
          />

          <GoupixDexEbaySoldCardSkeleton v-else-if="loading && !streamingListRows.length" :count="8" />

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

        <!-- Top results (cards / graded / sealed) -->
        <template v-else-if="!displayError">
          <template v-if="hasSearched && currentTopRows.length">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="text-muted text-sm">
                Top {{ currentTopRows.length }} {{ currentTopLabel }} — agrégés sur
                {{ topResult?.total_observed ?? 0 }} ventes analysées
                <span v-if="topScrape.cached.value" class="text-primary inline-flex items-center gap-1 font-medium">
                  · <UIcon name="i-lucide-zap" class="size-3.5" /> servi depuis le cache
                </span>
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
            v-else-if="hasSearched && topResult && !currentTopRows.length && !topLoading"
            color="info"
            variant="subtle"
            icon="i-lucide-search-x"
            :title="emptyTitle"
            :description="emptyDescription"
          />

          <GoupixDexEbaySoldTopSkeleton v-else-if="topLoading" :count="6" />

          <div
            v-else-if="!topResult"
            class="border-default/60 bg-elevated/20 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
          >
            <UIcon :name="emptyIcon" class="text-primary size-8" />
            <p class="text-highlighted text-sm font-medium">{{ topEmptyHeadline }}</p>
            <p class="text-muted max-w-md text-xs">
              {{ topEmptyHint }}
            </p>
            <UButton
              v-if="hasSearched"
              color="primary"
              variant="soft"
              icon="i-lucide-trophy"
              :disabled="q.trim().length < 2"
              @click.prevent="runLoad"
            >
              Calculer le top pour cette recherche
            </UButton>
          </div>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { TabsItem } from '@nuxt/ui'

import type { EbaySoldTopItem, EbaySoldTopResultBody, EbaySoldTopRow } from '~/composables/useEbaySoldTop'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Ventes terminées eBay',
  'Ventes terminées Pokémon TCG sur eBay France (page publique, sans scope Marketplace Insights).',
)

type ViewMode = 'list' | 'top-cards' | 'top-graded' | 'top-sealed'
type WindowKey = '24h' | '7d' | '30d'
type LanguageKey = 'any' | 'fr' | 'ja'

const windowOptions = [
  { label: 'Dernières 24 heures', value: '24h' as const },
  { label: '7 derniers jours', value: '7d' as const },
  { label: '30 derniers jours', value: '30d' as const },
]

const WINDOW_HOURS: Record<WindowKey, number> = {
  '24h': 24,
  '7d': 168,
  '30d': 720,
}

const languageOptions = [
  { label: 'Toutes les langues', value: 'any' as const },
  { label: 'Français', value: 'fr' as const },
  { label: 'Japonais', value: 'ja' as const },
]

const viewModeTabs: TabsItem[] = [
  { label: 'Liste des ventes', value: 'list', icon: 'i-lucide-list' },
  { label: 'Top cartes', value: 'top-cards', icon: 'i-lucide-layers' },
  { label: 'Top gradées', value: 'top-graded', icon: 'i-lucide-shield-check' },
  { label: 'Top scellés', value: 'top-sealed', icon: 'i-lucide-package' },
]

const q = ref('carte pokemon')
const windowKey = ref<WindowKey>('7d')
const languageKey = ref<LanguageKey>('any')
const viewMode = ref<ViewMode>('list')
/** True after the first explicit search — no auto-fetch on mount. */
const hasSearched = ref(false)

const windowHoursNum = computed(() => WINDOW_HOURS[windowKey.value])
const languageApiValue = computed<string | null>(() => (languageKey.value === 'any' ? null : languageKey.value))

const topScrape = useEbaySoldTop()
const topResult = topScrape.result

/**
 * Client-side cache keyed by (q, window) for tops — skips a POST when the user
 * returns to a search they just ran (the 15-minute server cache covers full page
 * reloads; this covers the current session).
 */
interface ClientTopCacheEntry {
  result: EbaySoldTopResultBody
  ebaySearchUrl: string | null
  fetchedAt: number
}
const topClientCache = new Map<string, ClientTopCacheEntry>()

function topCacheKey(qVal: string, win: WindowKey, lang: LanguageKey): string {
  return `${qVal.trim().toLowerCase()}|${win}|${lang}`
}

const listRows = computed<EbaySoldTopItem[]>(() => topResult.value?.items ?? [])
const streamingListRows = computed<EbaySoldTopItem[]>(() => topScrape.partialItems.value ?? [])
const totalObservedSoFar = computed<number>(() => topScrape.totalObservedSoFar.value)

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
    return "Essayez d'ajouter « PSA », « BGS » ou « CGC » à votre recherche, ou élargissez la fenêtre à 7 jours."
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

const topEmptyHeadline = computed(() => {
  if (hasSearched.value) {
    return "Le top n'est pas encore calculé pour cette recherche"
  }
  return 'Lancez une recherche pour générer le top'
})

const topEmptyHint = computed(() => {
  if (hasSearched.value) {
    return (
      "Le top demande une analyse plus profonde (jusqu'à 20 pages eBay) que la liste rapide. " +
      'Le résultat sera mis en cache 15 minutes côté serveur — utilisable instantanément ensuite.'
    )
  }
  return 'Le top fonctionne mieux avec des requêtes larges : « carte pokemon », « pokemon TCG », « Charizard ».'
})

const topLoading = computed(() => topScrape.loading.value)
const loading = topLoading

const progressPercent = computed(() => {
  const total = topScrape.pagesTotal.value
  const done = topScrape.pagesDone.value
  if (total <= 0) {
    return 0
  }
  return Math.min(100, Math.round((done / total) * 100))
})

const progressLabel = computed(() => {
  const total = topScrape.pagesTotal.value
  const done = topScrape.pagesDone.value
  if (topScrape.status.value === 'pending') {
    return 'Préparation de l’analyse eBay…'
  }
  if (total <= 0) {
    return 'Analyse eBay en cours…'
  }
  return `Analyse eBay — page ${done}/${total}`
})

const displayError = computed(() => topScrape.error.value ?? '')

/** eBay « vendus » search URL — usable even if the API is unreachable. */
const manualUrl = computed(() => {
  const fromApi = topScrape.ebaySearchUrl.value?.trim()
  if (fromApi) {
    return fromApi
  }
  const kw = encodeURIComponent(q.value.trim())
  let url = `https://www.ebay.fr/sch/i.html?_nkw=${kw}&LH_Sold=1&LH_Complete=1&_sop=13&_ipg=50&rt=nc`
  if (languageKey.value === 'fr') {
    url += '&Langue=Fran%C3%A7ais'
  } else if (languageKey.value === 'ja') {
    url += '&Langue=Japonais'
  }
  return url
})

/**
 * Trigger a search when pressing Enter in the keyword input.
 * @returns {void} Nothing.
 */
function onSearchEnter(): void {
  if (q.value.trim().length >= 2) {
    void runLoad()
  }
}

/**
 * Runs a single eBay analysis that feeds both the list and the three top tabs.
 * Switching tabs never refetches — it only filters ``topResult`` on the client.
 * @returns {Promise<void>} Resolves once the request finishes (success or error).
 */
async function runLoad(): Promise<void> {
  if (q.value.trim().length < 2) {
    return
  }
  hasSearched.value = true

  // Client cache: if we already have a result for (q, window, language), reuse it as-is
  // without calling the API.
  const key = topCacheKey(q.value, windowKey.value, languageKey.value)
  const cached = topClientCache.get(key)
  if (cached) {
    topScrape.cancel()
    topScrape.result.value = cached.result
    topScrape.ebaySearchUrl.value = cached.ebaySearchUrl
    topScrape.cached.value = true
    topScrape.status.value = 'completed'
    topScrape.pagesDone.value = cached.result.pages_requested
    topScrape.pagesTotal.value = cached.result.pages_requested
    topScrape.totalObservedSoFar.value = cached.result.total_observed
    topScrape.partialItems.value = cached.result.items
    return
  }

  const fresh = await topScrape.load({
    q: q.value,
    windowHours: windowHoursNum.value,
    pages: 20,
    scrapeLimit: 1000,
    topLimit: 20,
    minCount: 1,
    language: languageApiValue.value,
  })
  if (fresh) {
    topClientCache.set(key, {
      result: fresh,
      ebaySearchUrl: topScrape.ebaySearchUrl.value,
      fetchedAt: Date.now(),
    })
  }
}

onBeforeUnmount(() => {
  topScrape.cancel()
})
</script>
