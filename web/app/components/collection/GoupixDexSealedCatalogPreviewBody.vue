<template>
  <div class="space-y-5">
    <!-- Aperçu -->
    <div class="flex gap-4">
      <div class="bg-muted/20 flex size-24 shrink-0 items-center justify-center overflow-hidden rounded-xl">
        <img
          v-if="product.img"
          :src="product.img"
          :alt="product.full"
          class="h-full w-full object-contain"
          referrerpolicy="no-referrer"
          decoding="async"
        />
        <UIcon v-else :name="sealedProductTypeIcon(product.c)" class="text-muted size-9" />
      </div>
      <div class="min-w-0 flex-1">
        <p class="text-highlighted text-base leading-snug font-semibold">{{ product.n }}</p>
        <p class="text-muted mt-0.5 truncate text-sm">{{ expansionName }}</p>
        <div class="mt-2 flex flex-wrap items-center gap-1.5">
          <UBadge color="primary" variant="subtle" size="sm">{{ sealedProductTypeLabel(product.c) }}</UBadge>
          <UBadge v-if="ownedQuantity > 0" color="success" variant="subtle" size="sm" icon="i-lucide-check">
            Déjà ×{{ ownedQuantity }}
          </UBadge>
        </div>
      </div>
    </div>

    <!-- Prix marché -->
    <div class="border-default rounded-xl border p-3">
      <p class="app-label">Prix marché</p>
      <p class="text-highlighted mt-0.5 text-xl font-semibold tabular-nums">
        {{ displayPriceEur != null ? eur.format(displayPriceEur) : '—' }}
      </p>
    </div>

    <!-- Évolution du prix -->
    <section class="space-y-2">
      <div class="flex items-center justify-between">
        <p class="app-label">Évolution du prix</p>
        <span v-if="priceHistorySourceLabel" class="text-muted text-[10px]">{{ priceHistorySourceLabel }}</span>
      </div>
      <GoupixDexPriceHistoryChart :points="priceHistory?.points ?? []" />
    </section>

    <!-- Ajout -->
    <UButton color="primary" variant="solid" size="lg" icon="i-lucide-plus" block :loading="adding" @click="onAdd">
      {{ ownedQuantity > 0 ? 'Ajouter un exemplaire' : 'Ajouter à ma collection' }}
    </UButton>
  </div>
</template>

<script setup lang="ts">
import type { ComputedRef, PropType, Ref } from 'vue'
import type { SealedProduct, SealedProductType } from '~/composables/useSealed'
import type { SealedCatalogProduct } from '~/composables/useSealedCatalog'
import type { GoupixDexSealedCatalogPriceHistorySource } from '~/types/GoupixDexSealedCatalogPreviewBody'
import type { GoupixPriceHistoryResponse } from '~/types/PriceHistory'
import { sealedProductTypeIcon, sealedProductTypeLabel } from '~/utils/sealedProducts'

/**
 * Aperçu d'un produit du catalogue scellé (avant ajout) : prix, courbe, bouton d'ajout.
 */
const props = defineProps({
  product: {
    type: Object as PropType<SealedCatalogProduct>,
    required: true,
  },
  expansionName: {
    type: String,
    required: true,
  },
})

const emit = defineEmits<{
  added: [product: SealedProduct]
}>()

const { catalogAdd, catalogPriceHistory, quoteCatalogPrices } = useSealed()
const { loadProductPriceHistory } = useSealedCatalog()
const toast = useToast()

const priceHistory = ref<GoupixPriceHistoryResponse | null>(null)
const priceHistorySource: Ref<GoupixDexSealedCatalogPriceHistorySource | null> = ref(null)
const marketPriceEur = ref<number | null>(null)
const adding = ref(false)
const ownedQuantity = ref(0)

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

/** Prix marché Cardmarket (aligné sur les produits possédés), avec repli sur le prix catalogue. */
const displayPriceEur = computed<number | null>(() => marketPriceEur.value ?? props.product.price)

const priceHistorySourceLabel: ComputedRef<string | null> = computed(() => {
  if (priceHistorySource.value === 'tcgplayer') {
    return 'prix TCGplayer converti en €'
  }
  return priceHistory.value?.approximate ? 'tendance approximative' : null
})

/**
 * Charge la courbe : relevés Cardmarket du produit (API), sinon relevés TCGplayer du catalogue statique.
 * @returns Résolue quand la courbe est chargée ou l'échec acté.
 */
async function loadPriceHistory(): Promise<void> {
  let cardmarketHistory: GoupixPriceHistoryResponse | null = null
  try {
    cardmarketHistory = await catalogPriceHistory(props.product.p)
  } catch {
    cardmarketHistory = null
  }
  if (cardmarketHistory && cardmarketHistory.points.length >= 2) {
    priceHistory.value = cardmarketHistory
    priceHistorySource.value = 'cardmarket'
    return
  }
  const tcgplayerPoints = await loadProductPriceHistory(props.product.tp)
  if (tcgplayerPoints.length >= 2) {
    priceHistory.value = { points: tcgplayerPoints, approximate: false }
    priceHistorySource.value = 'tcgplayer'
    return
  }
  priceHistory.value = cardmarketHistory
  priceHistorySource.value = cardmarketHistory ? 'cardmarket' : null
}

/**
 * Résout le prix marché Cardmarket réel du produit (même source que les produits possédés).
 * @returns Résolue quand le prix est connu ou l'échec acté (repli catalogue).
 */
async function loadMarketPrice(): Promise<void> {
  if (props.product.p == null) {
    marketPriceEur.value = null
    return
  }
  try {
    const prices = await quoteCatalogPrices([props.product.p])
    marketPriceEur.value = prices[String(props.product.p)] ?? null
  } catch {
    marketPriceEur.value = null
  }
}

/**
 * Ajoute le produit à la collection (idempotent si apparié à Cardmarket).
 * @returns Résolue après ajout.
 */
async function onAdd(): Promise<void> {
  adding.value = true
  try {
    const res = await catalogAdd({
      name: props.product.n,
      product_type: props.product.c as SealedProductType,
      set_name: props.expansionName,
      cardmarket_id_product: props.product.p,
      image_url: props.product.img,
      market_price_eur: props.product.price,
    })
    ownedQuantity.value = res.product.quantity
    emit('added', res.product)
    toast.add({
      title: res.created ? 'Ajouté à ta collection' : `Quantité ×${res.product.quantity}`,
      description: props.product.full,
      color: 'success',
    })
  } catch (e) {
    toast.add({ title: 'Ajout impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    adding.value = false
  }
}

watch(
  () => props.product.tp,
  () => {
    ownedQuantity.value = 0
    marketPriceEur.value = null
    void loadPriceHistory()
    void loadMarketPrice()
  },
  { immediate: true },
)
</script>
