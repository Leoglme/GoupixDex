<template>
  <UDashboardPanel id="market">
    <template #header>
      <UDashboardNavbar title="Prix du marché">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/articles/create" color="primary" variant="soft" icon="i-lucide-plus"> Nouvel article </UButton>
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
              <p class="text-primary text-xs font-medium tracking-wide uppercase">Recherche en direct · eBay France</p>
              <h1 class="text-highlighted text-xl font-semibold tracking-tight sm:text-2xl">
                Évaluez un produit scellé ou une carte en quelques secondes
              </h1>
              <p class="text-muted text-sm leading-relaxed sm:text-base">
                GoupixDex interroge l'API eBay pour remonter les annonces actives correspondant à votre recherche, puis
                calcule automatiquement le prix minimum, médian, moyen et maximum — sur la période de votre choix.
              </p>
            </div>
            <div
              class="bg-primary/15 text-primary hidden size-24 shrink-0 items-center justify-center rounded-2xl lg:flex"
            >
              <UIcon name="i-lucide-trending-up" class="size-12" />
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

          <GoupixDexMarketSearchForm
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

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Prix du marché',
  'Analysez en direct les prix des cartes Pokémon et produits scellés sur eBay France : prix minimum, moyen, médian et maximum des annonces actives.',
)

const { loading, error, result, search } = useMarketSearch()
const toast = useToast()
const lastQuery = ref<string | null>(null)

/**
 * Run a market search and show a warning toast when the result set is empty.
 * @param input - Search form payload
 * @returns {Promise<void>} Resolves when the request finishes
 */
async function onSubmit(input: MarketSearchInput): Promise<void> {
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
 * Build `articles/create` query fields from a market listing row.
 * @param listing - Selected eBay row
 * @returns {Record<string, string>} Query key/value map
 */
function buildPrefillPayload(listing: MarketListing): Record<string, string> {
  const payload: Record<string, string> = {
    title: listing.title,
    purchase_price: String(listing.price_eur),
    condition: mapCondition(listing.condition, !!listing.graded),
  }
  const description = buildDescription(listing)
  if (description) {
    payload.description = description
  }
  const parsed = parseCardInfo(listing.title)
  if (parsed.pokemonName) {
    payload.pokemon_name = parsed.pokemonName
  }
  if (parsed.setCode) {
    payload.set_code = parsed.setCode
  }
  if (parsed.cardNumber) {
    payload.card_number = parsed.cardNumber
  }
  if (listing.image_url) {
    payload.image_url = listing.image_url
  }
  payload.source_url = listing.listing_url
  return payload
}

/**
 * Map eBay condition hints to GoupixDex article condition enum strings.
 * @param ebayCondition - Raw marketplace condition label
 * @param isGraded - Listing flagged as graded/slabbed
 * @returns {string} Internal condition label
 */
function mapCondition(ebayCondition: string, isGraded: boolean): string {
  if (isGraded) {
    return 'Mint'
  }
  const c = (ebayCondition || '').toLowerCase()
  if (c.includes('new') || c.includes('neuf') || c.includes('scellé') || c.includes('scelle')) {
    return 'Mint'
  }
  if (c.includes('like new') || c.includes('comme neuf')) {
    return 'Near Mint'
  }
  if (c.includes('excellent') || c.includes('très bon')) {
    return 'Excellent'
  }
  if (c.includes('good') || c.includes('bon')) {
    return 'Good'
  }
  if (c.includes('played') || c.includes('acceptable')) {
    return 'Played'
  }
  return 'Near Mint'
}

/**
 * Optional article description block copied from the marketplace listing.
 * @param listing - Selected listing row
 * @returns {string} Multi-line description text
 */
function buildDescription(listing: MarketListing): string {
  const lines: string[] = [listing.title]
  if (listing.condition) {
    lines.push('', `État eBay : ${listing.condition}`)
  }
  if (listing.graded) {
    lines.push(`Gradée ${listing.graded.grader}${listing.graded.grade ? ` ${listing.graded.grade}` : ''}`)
  }
  return lines.join('\n').trim()
}

const EXCLUDED_TOKENS = new Set([
  'NEW',
  'SEALED',
  'SCELLE',
  'SCELLÉ',
  'MINT',
  'NM',
  'EX',
  'EXCELLENT',
  'FR',
  'FRENCH',
  'FRANCAIS',
  'FRANÇAIS',
  'FRANCE',
  'ENGLISH',
  'ENG',
  'JP',
  'JAPAN',
  'JAPONAIS',
  'POKEMON',
  'POKÉMON',
  'PSA',
  'CGC',
  'BGS',
  'BECKETT',
  'GRADED',
  'VMAX',
  'VSTAR',
  'V',
  'GX',
  'EX',
  'TAG',
  'TEAM',
])

/**
 * Best-effort Pokémon name / set code / card number extraction from listing title tokens.
 * @param title - Full marketplace title string
 * @returns {{ pokemonName: string; setCode: string; cardNumber: string }} Parsed fragments
 */
function parseCardInfo(title: string): {
  pokemonName: string
  setCode: string
  cardNumber: string
} {
  const result = { pokemonName: '', setCode: '', cardNumber: '' }
  const numberMatch = title.match(/\b(\d{1,3})\s*\/\s*(\d{1,3})\b/)
  if (numberMatch) {
    result.cardNumber = numberMatch[1]!
  }
  const setMatch = title.match(
    /\b(SWSH\d{1,3}[a-z]?|SV\d{1,3}[a-z]?|SM\d{1,3}[a-z]?|BW\d{1,3}[a-z]?|XY\d{1,3}[a-z]?|EB\d{1,3}[a-z]?|EV\d{1,3}[a-z]?|BKS?\d{1,3}[a-z]?)\b/i,
  )
  if (setMatch) {
    result.setCode = setMatch[1]!.toUpperCase()
  }
  const cleaned = title.replace(/[^\p{L}\p{N}\s-]+/gu, ' ')
  const tokens = cleaned.split(/\s+/).filter(Boolean)
  for (const tok of tokens) {
    const upper = tok.toUpperCase()
    if (EXCLUDED_TOKENS.has(upper)) {
      continue
    }
    if (/^\d+$/.test(tok)) {
      continue
    }
    if (tok.length < 3) {
      continue
    }
    if (/^[A-ZÀ-ÖØ-Ý]/u.test(tok[0] ?? '')) {
      result.pokemonName = tok
      break
    }
  }
  return result
}

/**
 * Navigate to article creation with query params prefilled from the listing.
 * @param listing - Selected marketplace row
 * @returns {Promise<void>} Resolves after navigation is triggered
 */
async function onCreateArticle(listing: MarketListing): Promise<void> {
  const payload = buildPrefillPayload(listing)
  await navigateTo({ path: '/articles/create', query: payload })
}
</script>
