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

        <!-- Résultats -->
        <template v-else>
          <template v-if="hasSearched && rows.length">
            <p class="text-muted text-sm">
              {{ rows.length }} vente(s) dans la fenêtre. Tri d'origine eBay : terminées récemment.
            </p>
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <GoupixDexEbaySoldCard
                v-for="(row, idx) in rows"
                :key="row.item_id || `${idx}-${row.title.slice(0, 20)}`"
                :row="row"
              />
            </div>
          </template>

          <UAlert
            v-else-if="hasSearched && result && !rows.length && !loading"
            color="info"
            variant="subtle"
            icon="i-lucide-search-x"
            title="Aucune vente dans cette fenêtre"
            description="Essayez d'élargir à 7 jours ou reformulez la recherche."
          />

          <div v-else-if="loading" class="flex justify-center py-16">
            <UIcon name="i-lucide-loader-circle" class="text-primary size-10 animate-spin" />
          </div>

          <!-- État initial -->
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
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { EbaySoldScrapeRow } from '~/composables/useEbaySoldScrape'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Vendus eBay',
  'Ventes terminées Pokémon TCG sur eBay France (page publique, sans scope Marketplace Insights).',
)

const windowOptions = [
  { label: 'Dernières 24 heures', value: '24h' as const },
  { label: '7 derniers jours', value: '7d' as const },
]

const q = ref('carte pokemon')
const windowKey = ref<'24h' | '7d'>('24h')
/** True after the first explicit search — no auto-fetch on mount. */
const hasSearched = ref(false)

const windowHoursNum = computed(() => (windowKey.value === '24h' ? 24 : 168))

const { loading, error, result, load } = useEbaySoldScrape()

const rows = computed<EbaySoldScrapeRow[]>(() => result.value?.items ?? [])

/** eBay « vendus » search URL — usable even if the API is unreachable. */
const manualUrl = computed(() => {
  const fromApi = result.value?.ebay_sold_search_url?.trim()
  if (fromApi) {
    return fromApi
  }
  const kw = encodeURIComponent(q.value.trim())
  return `https://www.ebay.fr/sch/i.html?_nkw=${kw}&LH_Sold=1&LH_Complete=1&_sop=13&_ipg=50&rt=nc`
})

const displayError = computed(() => error.value ?? result.value?.error ?? '')

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
 * Submit a sold-listings scrape with the current keyword and window.
 *
 * @returns {Promise<void>} Resolves once the request finishes (success or error).
 */
async function runLoad(): Promise<void> {
  if (q.value.trim().length < 2) {
    return
  }
  hasSearched.value = true
  await load({
    q: q.value,
    windowHours: windowHoursNum.value,
    limit: 50,
  })
}
</script>
