<template>
  <UCard
    class="ring-default bg-elevated/30 border-[var(--app-accent)]/15 from-[var(--app-accent-soft)]/40 ring-1"
    :ui="{ body: 'p-4 sm:p-5 space-y-3' }"
  >
    <div class="flex items-start justify-between gap-2">
      <div>
        <p class="app-label !text-[0.62rem]">Prix & marge</p>
        <p class="text-highlighted mt-1 text-sm font-medium">Repères pour fixer votre prix de vente</p>
      </div>
      <UIcon
        v-if="loading"
        name="i-lucide-loader-2"
        class="text-primary size-5 shrink-0 animate-spin"
        aria-hidden="true"
      />
    </div>

    <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <div class="min-w-0 rounded-lg border border-[var(--app-line)] bg-[var(--app-surface)] px-3 py-2">
        <p class="truncate text-[10px] text-[var(--app-ink-soft)]">Cardmarket</p>
        <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ cardmarketLabel }}</p>
      </div>
      <div class="min-w-0 rounded-lg border border-[var(--app-line)] bg-[var(--app-surface)] px-3 py-2">
        <p class="truncate text-[10px] text-[var(--app-ink-soft)]">TCGPlayer</p>
        <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ tcgplayerLabel }}</p>
      </div>
      <div class="min-w-0 rounded-lg border border-[var(--app-line)] bg-[var(--app-surface)] px-3 py-2">
        <p class="truncate text-[10px] text-[var(--app-ink-soft)]">Votre achat</p>
        <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ purchaseLabel }}</p>
      </div>
      <div
        class="min-w-0 rounded-lg border border-[var(--app-accent)]/35 bg-[var(--app-accent-soft)] px-3 py-2 sm:col-span-1"
      >
        <p class="truncate text-[10px] text-[var(--app-accent-ink)]">
          Suggéré{{ marginPercent != null ? ` (+${marginPercent} %)` : '' }}
        </p>
        <p class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">{{ suggestedLabel }}</p>
      </div>
    </div>

    <p v-if="!hasCardIdentity" class="text-muted text-xs leading-relaxed">
      Renseignez le code set et le numéro de carte pour afficher le prix Cardmarket actuel.
    </p>
    <p v-else-if="pricing?.error" class="text-xs leading-relaxed text-amber-700 dark:text-amber-300">
      {{ pricingErrorText }}
    </p>

    <div
      v-if="orderContext"
      class="rounded-lg border border-[var(--app-line)] bg-[var(--app-surface)]/80 px-3 py-2 text-xs text-[var(--app-ink-soft)]"
    >
      <span class="font-medium text-[var(--app-ink)]">Ligne Cardmarket</span>
      — commande #{{ orderContext.external_order_id }}
      <span v-if="orderContext.unit_price_eur != null" class="tabular-nums">
        · payé {{ eur.format(orderContext.unit_price_eur) }}
      </span>
    </div>

    <div v-if="suggestedEur != null" class="flex flex-wrap items-center gap-2">
      <UButton size="sm" color="primary" variant="soft" icon="i-lucide-sparkles" @click="emitApplySuggested">
        Appliquer {{ eur.format(suggestedEur) }} en prix de vente
      </UButton>
      <NuxtLink
        v-if="marketLink"
        :to="marketLink"
        class="text-primary text-xs font-medium underline underline-offset-2"
      >
        Voir le marché eBay
      </NuxtLink>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'
import { DEFAULT_ARTICLE_MARKET_SEARCH_BASE, marketSearchToRouteQuery } from '~/utils/marketSearchQuery'
import type { MarketSearchInput } from '~/types/MarketSearch'

const props = defineProps<{
  setCode: string
  cardNumber: string
  pokemonName?: string
  purchasePrice?: number | null
  cachedCardmarketEur?: number | null
  cachedTcgplayerEur?: number | null
  orderContext?: Article['order_context']
}>()

const emit = defineEmits<{
  'apply-suggested': [priceEur: number]
}>()

const { lookup } = usePricing()

const pricing: Ref<PricingLookup | null> = ref(null)
const loading: Ref<boolean> = ref(false)

const eur = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 })

const hasCardIdentity = computed(() => Boolean(props.setCode?.trim() && props.cardNumber?.trim()))

const cardmarketEur = computed(() => pricing.value?.cardmarket_eur ?? props.cachedCardmarketEur ?? null)

const tcgplayerEur = computed(() => pricing.value?.tcgplayer_eur ?? props.cachedTcgplayerEur ?? null)

const marginPercent = computed(() => pricing.value?.margin_percent_used ?? null)

const suggestedEur = computed((): number | null => {
  if (pricing.value?.suggested_price_eur != null) {
    return pricing.value.suggested_price_eur
  }
  const cm = cardmarketEur.value
  if (cm == null) {
    return null
  }
  const margin = marginPercent.value ?? 20
  return Math.round(cm * (1 + margin / 100) * 100) / 100
})

const cardmarketLabel = computed(() => (cardmarketEur.value != null ? eur.format(cardmarketEur.value) : '—'))
const tcgplayerLabel = computed(() => (tcgplayerEur.value != null ? eur.format(tcgplayerEur.value) : '—'))
const purchaseLabel = computed(() =>
  props.purchasePrice != null && !Number.isNaN(props.purchasePrice) ? eur.format(props.purchasePrice) : '—',
)
const suggestedLabel = computed(() => (suggestedEur.value != null ? eur.format(suggestedEur.value) : '—'))

const pricingErrorText = computed(() => (pricing.value?.error ?? '').replace(/Pok[eé]Wallet/gi, 'catalogue externe'))

const marketLink = computed(() => {
  const q = [props.pokemonName, props.setCode, props.cardNumber].filter(Boolean).join(' ').trim()
  if (q.length < 2) {
    return null
  }
  const input: MarketSearchInput = { q, ...DEFAULT_ARTICLE_MARKET_SEARCH_BASE }
  return { path: '/market', query: marketSearchToRouteQuery(input, true) }
})

async function refreshPricing(): Promise<void> {
  if (!hasCardIdentity.value) {
    pricing.value = null
    return
  }
  loading.value = true
  try {
    pricing.value = await lookup(props.setCode.trim(), props.cardNumber.trim(), props.pokemonName ?? undefined)
  } catch {
    pricing.value = {
      error: 'Impossible de charger les prix.',
      cardmarket_eur: null,
      tcgplayer_usd: null,
      tcgplayer_eur: null,
      average_price_eur: null,
      suggested_price_eur: null,
      margin_percent_used: 20,
      set_name: null,
      source: null,
    }
  } finally {
    loading.value = false
  }
}

function emitApplySuggested(): void {
  if (suggestedEur.value != null) {
    emit('apply-suggested', suggestedEur.value)
  }
}

watch(
  () => [props.setCode, props.cardNumber] as const,
  () => {
    void refreshPricing()
  },
  { immediate: true },
)
</script>
