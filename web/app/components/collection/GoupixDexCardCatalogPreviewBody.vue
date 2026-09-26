<template>
  <div class="space-y-5">
    <!-- Aperçu carte -->
    <div class="flex justify-center">
      <div class="bg-muted/20 aspect-[63/88] w-44 overflow-hidden rounded-xl">
        <GoupixDexCardImage
          :image-url="previewImageUrl"
          :tcgdex-card-id="card.id"
          :alt="card.name"
          img-class="h-full w-full object-contain"
        />
      </div>
    </div>

    <div class="min-w-0 text-center">
      <p class="text-highlighted text-base leading-snug font-semibold">{{ card.name }}</p>
      <p class="text-muted mt-0.5 truncate text-sm">{{ card.setName }} · #{{ card.localId }}</p>
      <div class="mt-2 flex flex-wrap items-center justify-center gap-1.5">
        <UBadge color="primary" variant="subtle" size="sm">{{ languageLabel(card.locale) }}</UBadge>
        <UBadge v-if="ownedQuantity > 0" color="success" variant="subtle" size="sm" icon="i-lucide-check">
          Déjà ×{{ ownedQuantity }}
        </UBadge>
      </div>
    </div>

    <!-- Prix marché -->
    <div class="border-default rounded-xl border p-3">
      <div class="flex items-center justify-between">
        <p class="app-label">Prix marché</p>
        <span v-if="priceSourceLabel" class="text-muted text-[10px]">{{ priceSourceLabel }}</span>
      </div>
      <p class="text-highlighted mt-0.5 text-xl font-semibold tabular-nums">
        <UIcon v-if="loadingPrice" name="i-lucide-loader-2" class="size-4 animate-spin align-middle" />
        <template v-else>{{ displayPriceEur != null ? eur.format(displayPriceEur) : '—' }}</template>
      </p>
    </div>

    <!-- Évolution du prix -->
    <section class="space-y-2">
      <div class="flex items-center justify-between">
        <p class="app-label">Évolution du prix</p>
        <span v-if="priceHistory?.approximate" class="text-muted text-[10px]">tendance approximative</span>
      </div>
      <div
        v-if="loadingPrice"
        class="border-default flex h-40 items-center justify-center rounded-xl border border-dashed"
      >
        <UIcon name="i-lucide-loader-2" class="text-muted size-5 animate-spin" />
      </div>
      <GoupixDexPriceHistoryChart v-else :points="priceHistory?.points ?? []" />
    </section>

    <!-- Cardmarket -->
    <UButton
      :to="cardmarketLink"
      target="_blank"
      rel="noopener noreferrer"
      color="neutral"
      variant="subtle"
      size="md"
      icon="i-lucide-external-link"
      block
    >
      Voir sur Cardmarket
    </UButton>

    <!-- Prix d'achat (optionnel) -->
    <UFormField label="Prix d'achat (€)" hint="optionnel — pour suivre ta plus-value">
      <UInput v-model="purchaseText" type="number" min="0" step="0.01" placeholder="—" class="w-full" />
    </UFormField>

    <!-- Ajout -->
    <UButton color="primary" variant="solid" size="lg" icon="i-lucide-plus" block :loading="adding" @click="onAdd">
      {{ ownedQuantity > 0 ? 'Ajouter un exemplaire' : 'Ajouter à ma collection' }}
    </UButton>
  </div>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { CollectionCard } from '~/composables/useCollection'
import type { CatalogLocale } from '~/composables/useCardCatalog'
import type { GoupixCatalogCardRef } from '~/types/GoupixDrawerStack'
import type { GoupixPriceHistoryResponse } from '~/types/PriceHistory'
import { cardmarketUrl } from '~/utils/cards/cardmarketUrl'
import { parseEuroAmount } from '~/utils/sealedProducts'

/**
 * Aperçu d'une carte du catalogue TCGdex (avant ajout) : image, prix marché, bouton d'ajout.
 */
const props = defineProps<{
  card: GoupixCatalogCardRef
}>()

const emit = defineEmits<{
  added: [card: CollectionCard]
}>()

const { previewCard } = useCardCatalog()
const { addToCollection } = useCollection()
const toast = useToast()

const previewImageUrl = ref<string | null>(props.card.image)
const marketPriceEur = ref<number | null>(null)
const averagePriceEur = ref<number | null>(null)
const loadingPrice = ref(false)
const adding = ref(false)
const ownedQuantity = ref(0)
const purchaseText = ref('')
const cardmarketIdProduct: Ref<number | null> = ref<number | null>(null)
const priceHistory: Ref<GoupixPriceHistoryResponse | null> = ref<GoupixPriceHistoryResponse | null>(null)

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

/** Prix marché Cardmarket, avec repli sur la moyenne connue. */
const displayPriceEur = computed<number | null>(() => marketPriceEur.value ?? averagePriceEur.value)

/** Lien Cardmarket de la carte : fiche produit dès que l'aperçu connaît l'idProduct, recherche par nom + numéro avant. */
const cardmarketLink = computed<string>(() =>
  cardmarketUrl({ idProduct: cardmarketIdProduct.value, name: props.card.name, localId: props.card.localId }),
)

const priceSourceLabel = computed<string | null>(() => {
  if (marketPriceEur.value == null && averagePriceEur.value != null) {
    return 'prix moyen'
  }
  return null
})

/**
 * Libellé lisible d'une langue de carte.
 * @param code - Code langue (`fr` | `en` | `ja`).
 * @returns Le libellé français.
 */
function languageLabel(code: CatalogLocale): string {
  switch (code) {
    case 'fr':
      return 'Français'
    case 'en':
      return 'Anglais'
    case 'ja':
      return 'Japonais'
    default:
      return code
  }
}

/**
 * Charge le prix marché, l'image haute définition et la quantité déjà possédée via l'aperçu catalogue.
 * @returns Résolue quand l'aperçu est chargé ou l'échec acté.
 */
async function loadPreview(): Promise<void> {
  loadingPrice.value = true
  try {
    const data = await previewCard(props.card.id, null, props.card.locale)
    ownedQuantity.value = data.owned_quantity ?? 0
    marketPriceEur.value = data.pricing.cardmarket_eur
    averagePriceEur.value = data.pricing.average_price_eur
    cardmarketIdProduct.value = data.pricing.cardmarket_id_product ?? null
    priceHistory.value = data.price_history ?? null
    if (data.image_url_high) {
      previewImageUrl.value = data.image_url_high
    }
  } catch {
    marketPriceEur.value = null
    averagePriceEur.value = null
    priceHistory.value = null
  } finally {
    loadingPrice.value = false
  }
}

/**
 * Ajoute la carte à la collection (incrémente la quantité si déjà présente).
 * @returns Résolue après ajout.
 */
async function onAdd(): Promise<void> {
  adding.value = true
  try {
    const res = await addToCollection({
      tcgdex_card_id: props.card.id,
      language: props.card.locale,
      quantity: 1,
      purchase_price_eur: parseEuroAmount(purchaseText.value),
    })
    // Total possédé (toutes lignes) : la ligne incrémentée peut ne pas être la seule de cette carte.
    ownedQuantity.value = Math.max(ownedQuantity.value + 1, res.card.quantity)
    emit('added', res.card)
    toast.add({
      title: res.created ? 'Ajoutée à ta collection' : `Quantité ×${res.card.quantity}`,
      description: `${props.card.name} · ${languageLabel(props.card.locale)}`,
      color: 'success',
    })
  } catch (e) {
    toast.add({ title: 'Ajout impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    adding.value = false
  }
}

watch(
  () => props.card.id,
  () => {
    ownedQuantity.value = 0
    marketPriceEur.value = null
    averagePriceEur.value = null
    cardmarketIdProduct.value = null
    priceHistory.value = null
    purchaseText.value = ''
    previewImageUrl.value = props.card.image
    void loadPreview()
  },
  { immediate: true },
)
</script>
