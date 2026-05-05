<template>
  <UDashboardPanel :id="`article-view-${id}`">
    <template #header>
      <UDashboardNavbar title="Article">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex flex-wrap items-center gap-2">
            <UButton :to="`/articles/${id}/edit`" color="primary" icon="i-lucide-pencil"> Modifier </UButton>
            <UButton to="/articles/stock" color="neutral" variant="ghost" icon="i-lucide-package"> Mon stock </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-6 p-4 sm:p-6">
        <div v-if="loading" class="flex justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else-if="article">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0 space-y-1">
              <p class="text-primary text-xs font-medium tracking-wide uppercase">Fiche article</p>
              <h1 class="text-highlighted text-2xl font-semibold tracking-tight">
                {{ article.pokemon_name || article.title }}
              </h1>
              <p class="text-muted text-sm">{{ article.title }}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <UBadge :color="article.is_sold ? 'success' : 'warning'" variant="subtle">
                {{ article.is_sold ? 'Vendu' : 'En stock' }}
              </UBadge>
              <UBadge :color="(article.published_on_vinted ?? false) ? 'success' : 'error'" variant="subtle">
                {{ (article.published_on_vinted ?? false) ? 'Vinted oui' : 'Vinted' }}
              </UBadge>
              <UBadge :color="(article.published_on_ebay ?? false) ? 'success' : 'error'" variant="subtle">
                {{ (article.published_on_ebay ?? false) ? 'ebay oui' : 'ebay' }}
              </UBadge>
            </div>
          </div>

          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">Prix d'achat</p>
              <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                {{ eur.format(article.purchase_price) }}
              </p>
            </UCard>
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">Prix de vente</p>
              <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                {{ article.sell_price != null ? eur.format(article.sell_price) : '—' }}
              </p>
            </UCard>
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">Code set</p>
              <p class="text-highlighted mt-1 text-lg font-semibold">
                {{ article.set_code || '—' }}
              </p>
            </UCard>
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">N° carte</p>
              <p class="text-highlighted mt-1 text-lg font-semibold">
                {{ article.card_number || '—' }}
              </p>
            </UCard>
          </div>

          <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
            <div class="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
              <div class="min-w-0 flex-1 space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                  <p class="text-primary text-xs font-medium uppercase">Référence marché</p>
                  <UIcon
                    v-if="pricingLoading || ebayLoading"
                    name="i-lucide-loader-2"
                    class="text-primary size-7 shrink-0 animate-spin"
                  />
                </div>
                <p v-if="ebayMarketSummaryLine" class="text-muted text-xs leading-snug">
                  {{ ebayMarketSummaryLine }}
                </p>
              </div>
              <UButton
                :to="marketPageLink"
                color="neutral"
                variant="soft"
                size="sm"
                icon="i-lucide-trending-up"
                class="shrink-0"
              >
                Prix du marché
              </UButton>
            </div>

            <p v-if="!article.set_code?.trim() || !article.card_number?.trim()" class="text-muted text-sm">
              Renseignez le code set et le numéro de carte pour afficher les prix catalogue Cardmarket et TCGPlayer.
            </p>

            <UAlert
              v-if="pricing && pricing.error"
              color="warning"
              variant="subtle"
              icon="i-lucide-alert-triangle"
              title="Prix catalogue indisponibles"
              :description="pricing.error"
            />

            <UAlert
              v-if="ebayError"
              color="warning"
              variant="subtle"
              icon="i-lucide-alert-triangle"
              title="Prix eBay indisponibles"
              :description="ebayError"
            />

            <p v-if="ebayQueryTooShort" class="text-muted text-sm">
              Ajoutez un nom Pokémon, un code set ou un titre suffisamment descriptif pour estimer les prix eBay.
            </p>

            <div
              :class="[
                'grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4',
                showSuggestedPrice && pricing ? 'lg:grid-cols-3 xl:grid-cols-5' : 'lg:grid-cols-2 xl:grid-cols-4',
              ]"
            >
              <UCard class="bg-elevated/40 ring-default/60 min-w-0 ring-1" :ui="{ body: 'p-4' }">
                <p class="text-muted text-xs font-medium uppercase">Cardmarket</p>
                <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                  {{ cardmarketDisplay }}
                </p>
              </UCard>
              <UCard class="bg-elevated/40 ring-default/60 min-w-0 ring-1" :ui="{ body: 'p-4' }">
                <p class="text-muted text-xs font-medium uppercase">TCGPlayer</p>
                <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                  {{ tcgplayerDisplay }}
                </p>
              </UCard>
              <UCard class="bg-elevated/40 ring-default/60 min-w-0 ring-1" :ui="{ body: 'p-4' }">
                <p class="text-muted text-xs font-medium uppercase">eBay · prix min</p>
                <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                  {{ ebayMinDisplay }}
                </p>
              </UCard>
              <UCard class="bg-elevated/40 ring-default/60 min-w-0 ring-1" :ui="{ body: 'p-4' }">
                <p class="text-muted text-xs font-medium uppercase">eBay · moyenne</p>
                <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                  {{ ebayAvgDisplay }}
                </p>
              </UCard>
              <UCard
                v-if="showSuggestedPrice && pricing"
                class="border-primary/25 from-primary/10 ring-primary/20 min-w-0 bg-gradient-to-br to-transparent ring-1"
                :ui="{ body: 'p-4' }"
              >
                <p class="text-muted text-xs font-medium break-words hyphens-auto uppercase">
                  Prix suggéré (marge {{ pricing.margin_percent_used }} %)
                </p>
                <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                  {{ suggestedPriceFormatted }}
                </p>
              </UCard>
            </div>

            <div v-if="ebayMarket?.warnings?.length" class="space-y-1">
              <p class="text-muted text-xs font-medium">Remarques</p>
              <ul class="text-muted list-disc space-y-0.5 pl-4 text-xs">
                <li v-for="(w, i) in ebayMarket.warnings" :key="i">{{ w }}</li>
              </ul>
            </div>
          </UCard>

          <div :class="['flex flex-col gap-6', article.images?.length ? 'lg:flex-row lg:items-start lg:gap-8' : '']">
            <div
              :class="[
                'flex min-w-0 flex-col gap-4',
                article.images?.length ? 'w-full lg:min-w-0 lg:flex-1' : 'w-full',
              ]"
            >
              <UCard
                v-if="article.order_context"
                class="border-primary/25 from-primary/10 ring-primary/20 bg-gradient-to-br to-transparent ring-1"
                :ui="{ body: 'p-5 sm:p-6' }"
              >
                <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div class="space-y-1">
                    <p class="text-primary text-xs font-medium uppercase">Achat Cardmarket</p>
                    <p class="text-highlighted text-lg font-semibold">
                      Commande #{{ article.order_context.external_order_id }}
                    </p>
                    <p class="text-muted text-sm">
                      Payé le
                      {{
                        article.order_context.paid_at
                          ? new Date(article.order_context.paid_at).toLocaleDateString('fr-FR')
                          : '—'
                      }}
                      · Prix ligne {{ eur.format(article.order_context.unit_price_eur) }}
                    </p>
                    <p
                      v-if="article.order_context.seller_username"
                      class="text-muted flex flex-wrap items-center gap-x-2 gap-y-1 text-xs"
                    >
                      <span>Vendeur :</span>
                      <a
                        v-if="articleSellerProfileUrl"
                        :href="articleSellerProfileUrl"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-primary font-medium underline-offset-2 hover:underline"
                      >
                        {{ article.order_context.seller_username }}
                      </a>
                      <span v-else>{{ article.order_context.seller_username }}</span>
                      <img
                        v-if="articleOrderCountryFlagSrc"
                        :src="articleOrderCountryFlagSrc"
                        alt=""
                        width="20"
                        height="15"
                        class="inline-block h-[15px] w-5 shrink-0 rounded-sm object-cover"
                        loading="lazy"
                        decoding="async"
                      />
                      <span v-if="article.order_context.seller_country_code" class="sr-only">{{
                        article.order_context.seller_country_code
                      }}</span>
                    </p>
                  </div>
                  <UButton :to="`/orders/${article.order_context.order_id}`" icon="i-lucide-file-text" color="primary">
                    Voir la commande
                  </UButton>
                </div>
              </UCard>

              <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
                <p class="text-highlighted font-medium">Description</p>
                <p class="text-muted text-sm leading-relaxed whitespace-pre-wrap">
                  {{ article.description }}
                </p>
              </UCard>
            </div>

            <div
              v-if="article.images?.length"
              :class="[
                'min-w-0 space-y-3',
                (article.images?.length ?? 0) >= 3 ? 'lg:min-w-0 lg:flex-1' : 'lg:max-w-fit',
              ]"
            >
              <p class="text-highlighted text-sm font-medium">Photos</p>
              <div :class="articleImageGridClass">
                <img
                  v-for="img in article.images"
                  :key="img.id"
                  :src="imageSrc(img.image_url)"
                  :alt="article.title"
                  class="block h-auto max-h-72 w-auto max-w-full justify-self-start object-contain object-left sm:max-h-80"
                />
              </div>
            </div>
          </div>

          <div class="text-muted border-default flex flex-wrap gap-x-6 gap-y-2 border-t pt-4 text-xs">
            <span>Créé le {{ new Date(article.created_at).toLocaleString('fr-FR') }}</span>
            <span v-if="article.sold_at">Vendu le {{ new Date(article.sold_at).toLocaleString('fr-FR') }}</span>
          </div>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { MarketSearchInput, MarketSearchResponse } from '~/composables/useMarketSearch'
import type { PricingLookup } from '~/composables/usePricing'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'
import { DEFAULT_ARTICLE_MARKET_SEARCH_BASE, marketSearchToRouteQuery } from '~/utils/marketSearchQuery'
import { countryFlagImgUrl } from '~/utils/flagEmoji'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const config = useRuntimeConfig()
const { getArticle } = useArticles()
const { lookup } = usePricing()
const { search: searchEbayMarket, error: ebaySearchComposableError } = useMarketSearch()
const toast = useToast()

const article: Ref<Article | null> = ref(null)
const loading: Ref<boolean> = ref(true)
const pricing: Ref<PricingLookup | null> = ref(null)
const pricingLoading: Ref<boolean> = ref(false)
const ebayMarket: Ref<MarketSearchResponse | null> = ref(null)
const ebayLoading: Ref<boolean> = ref(false)
const ebayError: Ref<string | null> = ref(null)

const id: ComputedRef<number> = computed(() => Number(route.params.id))

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
})

const articleOrderCountryFlagSrc: ComputedRef<string | null> = computed(() =>
  article.value?.order_context?.seller_country_code
    ? countryFlagImgUrl(article.value.order_context.seller_country_code)
    : null,
)

const articleImageGridClass: ComputedRef<string> = computed(() => {
  const n = article.value?.images?.length ?? 0
  if (n <= 1) {
    return 'grid w-fit max-w-full grid-cols-1 gap-3'
  }
  if (n === 2) {
    return 'grid w-fit max-w-full grid-cols-1 gap-3 sm:grid-cols-2'
  }
  return 'grid w-full grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3'
})

const articleSellerProfileUrl: ComputedRef<string | null> = computed(() =>
  cardmarketSellerProfileUrl(article.value?.order_context?.seller_username ?? null),
)

/**
 * Router location for “Prix du marché” using the same query as this article’s eBay search (`auto=1`).
 */
const marketPageLink = computed(() => {
  if (!article.value) {
    return '/market'
  }
  const q = buildEbayMarketQuery(article.value)
  if (q.length < 2) {
    return '/market'
  }
  const input: MarketSearchInput = { q, ...DEFAULT_ARTICLE_MARKET_SEARCH_BASE }
  return { path: '/market', query: marketSearchToRouteQuery(input, true) }
})

/**
 * Build free-text query for eBay Browse from article identity fields (fallback: title).
 * @param a - Article row
 * @returns Query string (may be shorter than 2 characters)
 */
function buildEbayMarketQuery(a: Article): string {
  const parts: string[] = []
  if (a.pokemon_name?.trim()) {
    parts.push(a.pokemon_name.trim())
  }
  if (a.set_code?.trim()) {
    parts.push(a.set_code.trim())
  }
  if (a.card_number?.trim()) {
    parts.push(a.card_number.trim())
  }
  let q = parts.join(' ').trim()
  if (q.length < 2 && a.title?.trim()) {
    q = a.title.trim().slice(0, 256)
  }
  return q
}

const ebayQueryTooShort: ComputedRef<boolean> = computed(() => {
  if (!article.value || ebayLoading.value) {
    return false
  }
  return buildEbayMarketQuery(article.value).length < 2
})

/**
 * Prix suggéré côté UI : moyenne (Cardmarket + TCGPlayer EUR + eBay min) / 3, puis × (1 + marge %).
 * Aligné sur la marge utilisateur (identique à l’endpoint pricing pour la part « marge »).
 */
const suggestedPriceEurComputed: ComputedRef<number | null> = computed(() => {
  const p = pricing.value
  if (!p || p.error || pricingLoading.value || ebayLoading.value) {
    return null
  }
  const cm = p.cardmarket_eur
  const tcg = p.tcgplayer_eur
  const ebayMin = ebayMarket.value?.stats.min
  if (cm == null || tcg == null || ebayMin == null) {
    return null
  }
  const base = (cm + tcg + ebayMin) / 3
  const margin = p.margin_percent_used
  return Math.round(base * (1 + margin / 100) * 100) / 100
})

const showSuggestedPrice: ComputedRef<boolean> = computed(() => suggestedPriceEurComputed.value != null)

const suggestedPriceFormatted: ComputedRef<string> = computed(() => {
  const v = suggestedPriceEurComputed.value
  return v != null ? eur.format(v) : '—'
})

const cardmarketDisplay: ComputedRef<string> = computed(() => {
  const a = article.value
  if (!a?.set_code?.trim() || !a?.card_number?.trim()) {
    return '—'
  }
  if (pricingLoading.value) {
    return '—'
  }
  const p = pricing.value
  if (!p || p.error) {
    return '—'
  }
  return p.cardmarket_eur != null ? eur.format(p.cardmarket_eur) : '—'
})

const tcgplayerDisplay: ComputedRef<string> = computed(() => {
  const a = article.value
  if (!a?.set_code?.trim() || !a?.card_number?.trim()) {
    return '—'
  }
  if (pricingLoading.value) {
    return '—'
  }
  const p = pricing.value
  if (!p || p.error) {
    return '—'
  }
  return p.tcgplayer_eur != null ? eur.format(p.tcgplayer_eur) : '—'
})

const ebayMinDisplay: ComputedRef<string> = computed(() => {
  if (ebayLoading.value || ebayError.value) {
    return '—'
  }
  const a = article.value
  if (!a || buildEbayMarketQuery(a).length < 2) {
    return '—'
  }
  const min = ebayMarket.value?.stats.min
  return min != null ? eur.format(min) : '—'
})

const ebayAvgDisplay: ComputedRef<string> = computed(() => {
  if (ebayLoading.value || ebayError.value) {
    return '—'
  }
  const a = article.value
  if (!a || buildEbayMarketQuery(a).length < 2) {
    return '—'
  }
  const avg = ebayMarket.value?.stats.avg
  return avg != null ? eur.format(avg) : '—'
})

/** Sous-titre eBay sous « Référence marché » (échantillon agrégé). */
const ebayMarketSummaryLine: ComputedRef<string | null> = computed(() => {
  if (ebayError.value || !ebayMarket.value) {
    return null
  }
  const m = ebayMarket.value
  const count = m.stats.count
  const days = m.period_days
  const annonces =
    count > 1 ? `${count.toLocaleString('fr-FR')} annonces analysées publiées` : `1 annonce analysée publiée`
  const fenetre = days > 1 ? `au cours des ${days.toLocaleString('fr-FR')} derniers jours` : `au cours du dernier jour`
  return `Ebay: ${annonces} ${fenetre}.`
})

/**
 * Load PokéWallet reference prices when set code and card number are set on the article.
 * @param a - Loaded article row
 * @returns {Promise<void>} Nothing
 */
async function loadPricing(a: Article): Promise<void> {
  if (!a.set_code?.trim() || !a.card_number?.trim()) {
    pricing.value = null
    return
  }
  pricingLoading.value = true
  try {
    pricing.value = await lookup(a.set_code.trim(), a.card_number.trim(), a.pokemon_name)
  } catch (e) {
    pricing.value = {
      cardmarket_eur: null,
      tcgplayer_usd: null,
      tcgplayer_eur: null,
      average_price_eur: null,
      suggested_price_eur: null,
      margin_percent_used: 0,
      set_name: null,
      error: apiErrorMessage(e),
    }
  } finally {
    pricingLoading.value = false
  }
}

/**
 * Fetch aggregated eBay France stats for the article search query.
 * @param a - Article row
 * @returns {Promise<void>} Nothing
 */
async function loadEbayMarket(a: Article): Promise<void> {
  const q = buildEbayMarketQuery(a)
  if (q.length < 2) {
    ebayMarket.value = null
    ebayError.value = null
    return
  }
  ebayLoading.value = true
  ebayError.value = null
  ebayMarket.value = null
  try {
    const res = await searchEbayMarket({
      q,
      ...DEFAULT_ARTICLE_MARKET_SEARCH_BASE,
    })
    ebayMarket.value = res
    if (!res) {
      ebayError.value = ebaySearchComposableError.value || 'Impossible de récupérer les prix eBay.'
    }
  } finally {
    ebayLoading.value = false
  }
}

async function load(): Promise<void> {
  loading.value = true
  pricing.value = null
  ebayMarket.value = null
  ebayError.value = null
  try {
    article.value = await getArticle(id.value)
  } catch (e) {
    toast.add({ title: 'Article introuvable', description: apiErrorMessage(e), color: 'error' })
    await navigateTo('/articles')
  } finally {
    loading.value = false
  }
  if (article.value) {
    const a = article.value
    await Promise.all([loadPricing(a), loadEbayMarket(a)])
  }
}

/**
 * Resolve image URL for preview (same rules as the article form).
 * @param url - Stored path or absolute URL.
 * @returns Display URL.
 */
function imageSrc(url: string): string {
  if (url.startsWith('http')) {
    return url
  }
  return `${config.public.apiBase}${url}`
}

useSeoMeta({
  title: computed(() =>
    article.value ? `${article.value.title.slice(0, 48)} · Article · GoupixDex` : 'Article · GoupixDex',
  ),
  description: computed(() =>
    article.value
      ? `Détail de « ${article.value.title} » : prix, photos et lien commande Cardmarket éventuel.`
      : 'Fiche article GoupixDex.',
  ),
})

onMounted((): void => {
  void load()
})
</script>
