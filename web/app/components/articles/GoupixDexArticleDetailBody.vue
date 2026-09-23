<template>
  <div :class="embedded ? 'space-y-4' : 'w-full space-y-6 p-4 sm:p-6'">
    <div v-if="loading" class="flex justify-center py-12">
      <UIcon name="i-lucide-loader-circle" class="h-8 w-8 animate-spin text-[var(--app-accent)]" />
    </div>

    <template v-else-if="article">
      <div v-if="!embedded" class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div class="min-w-0 flex-1 space-y-1">
          <p class="text-primary text-xs font-medium tracking-wide uppercase">Fiche article</p>
          <h1 class="text-highlighted text-2xl font-semibold tracking-tight">
            {{ article.pokemon_name || article.title }}
          </h1>
          <p class="text-muted text-sm">{{ article.title }}</p>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <UBadge :color="article.is_sold ? 'success' : 'warning'" variant="subtle">
            {{ article.is_sold ? 'Vendu' : 'En vente' }}
          </UBadge>
        </div>
      </div>

      <div v-if="showMarketplaceActions" class="flex w-full gap-2">
        <GoupixDexMarketplaceDelistButton
          v-if="article.published_on_ebay"
          class="min-w-0 flex-1"
          marketplace="ebay"
          :loading="removingEbay"
          :disabled="removingVinted"
          @click="onRemoveEbay"
        />
        <GoupixDexMarketplaceDelistButton
          v-if="article.published_on_vinted"
          class="min-w-0 flex-1"
          marketplace="vinted"
          :loading="removingVinted"
          :disabled="removingEbay"
          @click="onRemoveVinted"
        />
      </div>

      <div
        v-if="
          (article.cross_ebay_removal_failed && article.published_on_ebay) ||
          (article.cross_vinted_removal_failed && article.published_on_vinted)
        "
        class="space-y-2"
      >
        <UAlert
          v-if="article.cross_ebay_removal_failed && article.published_on_ebay"
          color="warning"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Dernière suppression eBay échouée"
          :description="article.cross_ebay_removal_error || 'Réessayez avec le bouton ci-dessus.'"
        />
        <UAlert
          v-if="article.cross_vinted_removal_failed && article.published_on_vinted"
          color="warning"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Dernière suppression Vinted échouée"
          :description="article.cross_vinted_removal_error || 'Réessayez avec le bouton ci-dessus.'"
        />
      </div>

      <section class="space-y-2">
        <p class="app-label">Vente & fiche</p>
        <div class="grid grid-cols-2 gap-2">
          <div class="rounded-lg border border-[var(--app-line)] bg-[var(--app-surface-2)]/50 px-3 py-2">
            <p class="text-[10px] text-[var(--app-ink-soft)]">Prix d'achat</p>
            <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">
              {{ eur.format(article.purchase_price) }}
            </p>
          </div>
          <div class="rounded-lg border border-[var(--app-line)] bg-[var(--app-surface-2)]/50 px-3 py-2">
            <p class="text-[10px] text-[var(--app-ink-soft)]">Prix de vente</p>
            <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">
              {{ article.sell_price != null ? eur.format(article.sell_price) : '—' }}
            </p>
          </div>
          <div class="rounded-lg border border-[var(--app-line)] bg-[var(--app-surface-2)]/50 px-3 py-2">
            <p class="text-[10px] text-[var(--app-ink-soft)]">Set</p>
            <p class="truncate text-sm font-semibold text-[var(--app-ink)]">
              {{ article.set_code || '—' }}
            </p>
          </div>
          <div class="rounded-lg border border-[var(--app-line)] bg-[var(--app-surface-2)]/50 px-3 py-2">
            <p class="text-[10px] text-[var(--app-ink-soft)]">N° carte</p>
            <p class="truncate text-sm font-semibold text-[var(--app-ink)] tabular-nums">
              {{ article.card_number || '—' }}
            </p>
          </div>
        </div>
        <button
          v-if="article.collection_card_id"
          type="button"
          class="flex w-full items-center justify-between gap-2 rounded-lg border border-[var(--app-line)] bg-[var(--app-surface-2)]/50 px-3 py-2 text-left transition-colors hover:bg-[var(--app-surface-2)]"
          @click="openLinkedCollectionCard"
        >
          <span class="flex min-w-0 items-center gap-2 text-sm text-[var(--app-ink)]">
            <UIcon name="i-lucide-album" class="size-4 shrink-0 text-[var(--app-ink-soft)]" />
            Dans ma collection
          </span>
          <span class="text-primary shrink-0 text-sm">Voir la carte</span>
        </button>
      </section>

      <section class="space-y-2 border-t border-[var(--app-line-soft)] pt-4">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <p class="app-label">Référence marché</p>
              <UIcon
                v-if="showMarketReferenceSpinner"
                name="i-lucide-loader-2"
                class="size-4 shrink-0 animate-spin text-[var(--app-accent)]"
              />
            </div>
            <p v-if="ebayMarketSummaryLine" class="mt-1 text-[11px] leading-snug text-[var(--app-ink-soft)]">
              {{ ebayMarketSummaryLine }}
            </p>
          </div>
          <UButton
            :to="marketPageLink"
            color="neutral"
            variant="subtle"
            size="xs"
            icon="i-lucide-trending-up"
            class="shrink-0"
          >
            Marché
          </UButton>
        </div>

        <p v-if="!article.set_code?.trim() || !article.card_number?.trim()" class="text-xs text-[var(--app-ink-soft)]">
          Renseignez le set et le n° pour Cardmarket / TCGPlayer.
        </p>

        <UAlert
          v-if="pricing && pricing.error && !pricing.cardmarket_eur"
          :color="pricing.source === 'cardmarket_local' ? 'neutral' : 'warning'"
          variant="subtle"
          :icon="pricing.source === 'cardmarket_local' ? 'i-lucide-info' : 'i-lucide-alert-triangle'"
          title="Prix Cardmarket / TCGPlayer indisponibles"
          :description="pricingErrorDescription"
        />

        <UAlert
          v-if="ebayError"
          color="warning"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Prix eBay indisponibles"
          :description="ebayError"
        />

        <p v-if="ebayQueryTooShort" class="text-xs text-[var(--app-ink-soft)]">
          Ajoutez un nom, un set ou un titre plus explicite pour estimer eBay.
        </p>

        <div class="grid grid-cols-2 gap-2">
          <div class="min-w-0 rounded-lg border border-[var(--app-line)] px-3 py-2">
            <p class="truncate text-[10px] text-[var(--app-ink-soft)]" title="Cardmarket">Cardmarket</p>
            <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ cardmarketDisplay }}</p>
          </div>
          <div class="min-w-0 rounded-lg border border-[var(--app-line)] px-3 py-2">
            <p class="truncate text-[10px] text-[var(--app-ink-soft)]" title="TCGPlayer">TCGPlayer</p>
            <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ tcgplayerDisplay }}</p>
          </div>
          <div class="min-w-0 rounded-lg border border-[var(--app-line)] px-3 py-2">
            <p class="truncate text-[10px] text-[var(--app-ink-soft)]">eBay · min</p>
            <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ ebayMinDisplay }}</p>
          </div>
          <div class="min-w-0 rounded-lg border border-[var(--app-line)] px-3 py-2">
            <p class="truncate text-[10px] text-[var(--app-ink-soft)]">eBay · moy.</p>
            <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ ebayAvgDisplay }}</p>
          </div>
          <div
            v-if="showSuggestedPrice && pricing"
            class="col-span-2 rounded-lg border border-[var(--app-accent)]/30 bg-[var(--app-accent-soft)] px-3 py-2"
          >
            <p class="text-[10px] text-[var(--app-accent-ink)]">
              Prix suggéré (marge {{ pricing.margin_percent_used }} %)
            </p>
            <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ suggestedPriceFormatted }}</p>
          </div>
        </div>

        <ul
          v-if="ebayMarket?.warnings?.length"
          class="list-disc space-y-0.5 pl-4 text-[11px] text-[var(--app-ink-soft)]"
        >
          <li v-for="(w, i) in ebayMarket.warnings" :key="i">{{ w }}</li>
        </ul>
      </section>

      <div
        :class="
          embedded
            ? 'flex flex-col gap-4 border-t border-[var(--app-line-soft)] pt-4'
            : ['flex flex-col gap-6', article.images?.length ? 'lg:flex-row lg:items-start lg:gap-8' : '']
        "
      >
        <div v-if="embedded && article.images?.length" class="space-y-2">
          <p class="app-label">Photos</p>
          <div :class="articleImageGridClass">
            <button
              v-for="(img, i) in article.images"
              :key="img.id"
              type="button"
              class="inline-flex shrink-0 cursor-zoom-in border-0 bg-transparent p-0 transition-opacity hover:opacity-90"
              :class="embedded ? 'max-w-[calc(50%-0.25rem)]' : 'self-start'"
              :aria-label="`Voir la photo ${i + 1} en grand`"
              @click="openArticleLightbox(i)"
            >
              <img :src="imageSrc(img.image_url)" :alt="article.title" :class="articleImageClass" draggable="false" />
            </button>
          </div>
        </div>

        <div
          :class="[
            'flex w-full min-w-0 flex-col gap-4',
            !embedded && article.images?.length ? 'lg:min-w-0 lg:flex-1' : '',
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

          <UCard class="ring-default ring-1" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
            <p class="text-highlighted font-medium">Description</p>
            <p class="text-muted text-sm leading-relaxed whitespace-pre-wrap">
              {{ article.description }}
            </p>
          </UCard>
        </div>

        <div
          v-if="!embedded && article.images?.length"
          :class="['min-w-0 space-y-3', (article.images?.length ?? 0) >= 3 ? 'lg:min-w-0 lg:flex-1' : 'lg:max-w-fit']"
        >
          <p class="text-highlighted text-sm font-medium">Photos</p>
          <div :class="articleImageGridClass">
            <button
              v-for="(img, i) in article.images"
              :key="img.id"
              type="button"
              class="inline-flex shrink-0 cursor-zoom-in border-0 bg-transparent p-0 transition-opacity hover:opacity-90"
              :class="embedded ? 'max-w-[calc(50%-0.25rem)]' : 'self-start'"
              :aria-label="`Voir la photo ${i + 1} en grand`"
              @click="openArticleLightbox(i)"
            >
              <img :src="imageSrc(img.image_url)" :alt="article.title" :class="articleImageClass" draggable="false" />
            </button>
          </div>
        </div>
      </div>

      <div class="text-muted border-default flex flex-wrap gap-x-6 gap-y-2 border-t pt-4 text-xs">
        <span>Créé le {{ new Date(article.created_at).toLocaleString('fr-FR') }}</span>
        <span v-if="article.sold_at">Vendu le {{ new Date(article.sold_at).toLocaleString('fr-FR') }}</span>
      </div>

      <GoupixDexImageLightbox v-model="articleLightboxIndex" :photos="articleLightboxPhotos" />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import { apiErrorMessage } from '~/composables/useApiError'
import type { MarketSearchInput, MarketSearchResponse } from '~/composables/useMarketSearch'
import type { PricingLookup } from '~/composables/usePricing'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'
import { DEFAULT_ARTICLE_MARKET_SEARCH_BASE, marketSearchToRouteQuery } from '~/utils/marketSearchQuery'
import { countryFlagImgUrl } from '~/utils/flagEmoji'

const props = withDefaults(
  defineProps<{
    articleId: number
    /** Contenu affiché dans le drawer (sans en-tête « Fiche article » dupliqué). */
    embedded?: boolean
  }>(),
  {
    embedded: false,
  },
)

const emit = defineEmits<{
  updated: [article: Article]
}>()

const config = useRuntimeConfig()
const { getArticle, removeEbayListing, removeVintedListing } = useArticles()
const { isDesktopApp } = useDesktopRuntime()
const { lookup } = usePricing()
const { search: searchEbayMarket, error: ebaySearchComposableError } = useMarketSearch()
const toast = useToast()
const { confirm: confirmAction } = useGoupixConfirm()
const { openCard } = useOpenCardDrawer()

const article: Ref<Article | null> = ref(null)
const loading: Ref<boolean> = ref(true)
const pricing: Ref<PricingLookup | null> = ref(null)
const pricingLoading: Ref<boolean> = ref(false)
const ebayMarket: Ref<MarketSearchResponse | null> = ref(null)
const ebayLoading: Ref<boolean> = ref(false)
const ebayError: Ref<string | null> = ref(null)
const removingEbay: Ref<boolean> = ref(false)
const removingVinted: Ref<boolean> = ref(false)

const id: ComputedRef<number> = computed(() => props.articleId)

const showMarketplaceActions: ComputedRef<boolean> = computed(() =>
  Boolean(article.value?.published_on_ebay || article.value?.published_on_vinted),
)

/** Spinner only while eBay loads, or pricing lookup when Cardmarket is not cached on the article. */
const showMarketReferenceSpinner: ComputedRef<boolean> = computed(() => {
  if (ebayLoading.value) {
    return true
  }
  if (pricingLoading.value && article.value?.market_cardmarket_eur == null) {
    return true
  }
  return false
})

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
  if (props.embedded) {
    return 'flex flex-wrap items-start gap-2'
  }
  if (n <= 1) {
    return 'grid w-fit max-w-full grid-cols-1 items-start gap-3'
  }
  if (n === 2) {
    return 'grid w-fit max-w-full grid-cols-1 items-start gap-3 sm:grid-cols-2'
  }
  return 'grid w-full grid-cols-1 items-start gap-3 sm:grid-cols-2 lg:grid-cols-3'
})

const articleImageClass: ComputedRef<string> = computed(() =>
  props.embedded
    ? 'block max-h-40 w-auto max-w-full shrink-0 rounded-lg object-contain ring-1 ring-[var(--app-line)]'
    : 'block h-auto max-h-72 w-auto max-w-full self-start object-contain object-left sm:max-h-80',
)

const articleLightboxIndex: Ref<number | null> = ref(null)

const articleLightboxPhotos: ComputedRef<string[]> = computed(() =>
  (article.value?.images ?? []).map((img) => imageSrc(img.image_url)),
)

function openArticleLightbox(index: number): void {
  articleLightboxIndex.value = index
}

/**
 * Ouvre la carte de « Ma collection » reliée à cet article, par-dessus dans la même pile de drawers.
 * @returns {void}
 */
function openLinkedCollectionCard(): void {
  const collectionCardId = article.value?.collection_card_id
  if (collectionCardId != null) {
    openCard(collectionCardId)
  }
}

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

const pricingErrorDescription: ComputedRef<string> = computed(() => {
  const msg = pricing.value?.error?.trim()
  if (!msg) {
    return ''
  }
  return msg.replace(/Pok[eé]Wallet/gi, 'catalogue externe')
})

const cardmarketDisplay: ComputedRef<string> = computed(() => {
  const a = article.value
  if (!a?.set_code?.trim() || !a?.card_number?.trim()) {
    return '—'
  }
  if (a.market_cardmarket_eur != null) {
    return eur.format(a.market_cardmarket_eur)
  }
  if (pricingLoading.value) {
    return '—'
  }
  const p = pricing.value
  if (!p) {
    return '—'
  }
  return p.cardmarket_eur != null ? eur.format(p.cardmarket_eur) : '—'
})

const tcgplayerDisplay: ComputedRef<string> = computed(() => {
  const a = article.value
  if (!a?.set_code?.trim() || !a?.card_number?.trim()) {
    return '—'
  }
  if (a.market_tcgplayer_eur != null) {
    return eur.format(a.market_tcgplayer_eur)
  }
  if (pricingLoading.value) {
    return '—'
  }
  const p = pricing.value
  if (!p) {
    return '—'
  }
  return p.tcgplayer_eur != null ? eur.format(p.tcgplayer_eur) : '—'
})

function parseListingPriceEur(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
    return value
  }
  if (typeof value === 'string') {
    const n = parseFloat(value.trim().replace(',', '.'))
    return Number.isFinite(n) && n > 0 ? n : null
  }
  return null
}

function ebayPricesFromItems(): number[] {
  const items = ebayMarket.value?.items ?? []
  const prices: number[] = []
  for (const row of items) {
    const p = parseListingPriceEur(row.price_eur)
    if (p != null) {
      prices.push(p)
    }
  }
  return prices
}

function resolveEbayStat(kind: 'min' | 'avg'): number | null {
  const m = ebayMarket.value
  if (!m) {
    return null
  }
  const fromStats = kind === 'min' ? m.stats.min : kind === 'avg' ? m.stats.avg : m.stats.median
  if (fromStats != null && fromStats > 0) {
    return fromStats
  }
  const prices = ebayPricesFromItems()
  if (!prices.length) {
    return null
  }
  if (kind === 'min') {
    return Math.min(...prices)
  }
  const sum = prices.reduce((acc, p) => acc + p, 0)
  return Math.round((sum / prices.length) * 100) / 100
}

const ebayMinDisplay: ComputedRef<string> = computed(() => {
  if (ebayLoading.value || ebayError.value) {
    return '—'
  }
  const a = article.value
  if (!a || buildEbayMarketQuery(a).length < 2) {
    return '—'
  }
  const min = resolveEbayStat('min')
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
  const avg = resolveEbayStat('avg')
  return avg != null ? eur.format(avg) : '—'
})

/** Sous-titre eBay sous « Référence marché » (échantillon agrégé). */
const ebayMarketSummaryLine: ComputedRef<string | null> = computed(() => {
  if (ebayError.value || !ebayMarket.value) {
    return null
  }
  const m = ebayMarket.value
  const pricedCount = m.stats.count
  const listingCount = m.items?.length ?? 0
  const days = m.period_days
  const fenetre = days > 1 ? `au cours des ${days.toLocaleString('fr-FR')} derniers jours` : `au cours du dernier jour`

  if (pricedCount > 0) {
    const annonces =
      pricedCount > 1 ? `${pricedCount.toLocaleString('fr-FR')} annonces avec prix` : `1 annonce avec prix`
    return `eBay : ${annonces} ${fenetre}.`
  }
  if (listingCount > 0) {
    return `eBay : ${listingCount.toLocaleString('fr-FR')} annonce(s) trouvée(s) ${fenetre}, sans prix exploitable dans l’échantillon.`
  }
  if ((m.total_matches ?? 0) > 0) {
    return `eBay : correspondances trouvées ${fenetre}, mais aucune annonce détaillée avec prix.`
  }
  return null
})

function seedPricingFromArticle(a: Article): void {
  if (a.market_cardmarket_eur == null && a.market_tcgplayer_eur == null) {
    return
  }
  pricing.value = {
    cardmarket_eur: a.market_cardmarket_eur ?? null,
    tcgplayer_eur: a.market_tcgplayer_eur ?? null,
    tcgplayer_usd: null,
    average_price_eur: null,
    suggested_price_eur: null,
    margin_percent_used: pricing.value?.margin_percent_used ?? 20,
    set_name: null,
    source: 'cardmarket_local',
    error: null,
  }
}

/**
 * Load reference prices when set + number exist. Skips the Cardmarket spinner when cached on the article.
 * @param a - Loaded article row
 * @returns {Promise<void>} Nothing
 */
async function loadPricing(a: Article): Promise<void> {
  if (!a.set_code?.trim() || !a.card_number?.trim()) {
    pricing.value = null
    return
  }
  const background = a.market_cardmarket_eur != null
  if (!background) {
    pricingLoading.value = true
  }
  try {
    const p = await lookup(a.set_code.trim(), a.card_number.trim(), a.pokemon_name)
    pricing.value = {
      ...p,
      cardmarket_eur: a.market_cardmarket_eur ?? p.cardmarket_eur,
      tcgplayer_eur: a.market_tcgplayer_eur ?? p.tcgplayer_eur,
    }
  } catch (e) {
    if (!background) {
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

async function reloadArticle(): Promise<void> {
  article.value = await getArticle(id.value)
  if (article.value) {
    emit('updated', article.value)
  }
}

async function onRemoveEbay(): Promise<void> {
  if (!article.value?.published_on_ebay) {
    return
  }
  const okEbay = await confirmAction({
    title: 'Retirer l’annonce eBay ?',
    body: 'L’annonce sera retirée du marketplace. La fiche GoupixDex sera conservée.',
    confirmLabel: 'Retirer de eBay',
    confirmColor: 'error',
  })
  if (!okEbay) {
    return
  }
  removingEbay.value = true
  try {
    article.value = await removeEbayListing(id.value)
    emit('updated', article.value)
    toast.add({ title: 'Annonce eBay retirée', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Suppression eBay', description: apiErrorMessage(e), color: 'error' })
    try {
      await reloadArticle()
    } catch {
      /* ignore */
    }
  } finally {
    removingEbay.value = false
  }
}

async function onRemoveVinted(): Promise<void> {
  if (!article.value?.published_on_vinted) {
    return
  }
  if (!isDesktopApp.value) {
    toast.add({
      title: 'Application desktop requise',
      description: 'La suppression Vinted s’exécute sur le worker local (app GoupixDex).',
      color: 'warning',
    })
    return
  }
  const okVinted = await confirmAction({
    title: 'Retirer l’annonce Vinted ?',
    body: 'Chrome va s’ouvrir sur ce poste pour retirer l’annonce. La fiche GoupixDex sera conservée.',
    confirmLabel: 'Retirer de Vinted',
    confirmColor: 'error',
  })
  if (!okVinted) {
    return
  }
  removingVinted.value = true
  try {
    await removeVintedListing(id.value)
    toast.add({
      title: 'Vinted',
      description: 'Suppression lancée sur ce poste. Actualisation dans quelques secondes…',
      color: 'neutral',
    })
    setTimeout(() => {
      void reloadArticle()
        .then(() => {
          if (!article.value?.published_on_vinted) {
            toast.add({ title: 'Annonce Vinted retirée', color: 'success' })
          }
        })
        .catch(() => {})
    }, 7000)
  } catch (e) {
    const msg = apiErrorMessage(e)
    if (msg.includes('VINTED_LOCAL_WORKER_REQUIRED')) {
      toast.add({
        title: 'Application desktop requise',
        description: 'Ouvrez GoupixDex en version desktop pour retirer l’annonce Vinted.',
        color: 'warning',
      })
    } else {
      toast.add({ title: 'Suppression Vinted', description: msg, color: 'error' })
    }
    try {
      await reloadArticle()
    } catch {
      /* ignore */
    }
  } finally {
    removingVinted.value = false
  }
}

async function load(): Promise<void> {
  loading.value = true
  pricing.value = null
  ebayMarket.value = null
  ebayError.value = null
  try {
    article.value = await getArticle(id.value)
    if (article.value) {
      seedPricingFromArticle(article.value)
    }
  } catch (e) {
    toast.add({ title: 'Article introuvable', description: apiErrorMessage(e), color: 'error' })
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

watch(
  id,
  () => {
    articleLightboxIndex.value = null
    void load()
  },
  { immediate: true },
)
</script>
