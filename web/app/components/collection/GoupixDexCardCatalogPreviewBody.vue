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

    <!-- Ajout -->
    <UButton color="primary" variant="solid" size="lg" icon="i-lucide-plus" block :loading="adding" @click="onAdd">
      {{ ownedQuantity > 0 ? 'Ajouter un exemplaire' : 'Ajouter à ma collection' }}
    </UButton>
  </div>
</template>

<script setup lang="ts">
import type { CollectionCard } from '~/composables/useCollection'
import type { CatalogLocale } from '~/composables/useCardCatalog'
import type { GoupixCatalogCardRef } from '~/types/GoupixDrawerStack'
import { cardmarketUrl } from '~/utils/cards/cardmarketUrl'

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

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

/** Prix marché Cardmarket, avec repli sur la moyenne connue. */
const displayPriceEur = computed<number | null>(() => marketPriceEur.value ?? averagePriceEur.value)

/** Lien Cardmarket de la carte (recherche par nom + numéro, l'idProduct n'étant pas exposé au catalogue). */
const cardmarketLink = computed<string>(() => cardmarketUrl({ name: props.card.name, localId: props.card.localId }))

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
 * Charge le prix marché et l'image haute définition via l'aperçu catalogue.
 * @returns Résolue quand l'aperçu est chargé ou l'échec acté.
 */
async function loadPreview(): Promise<void> {
  loadingPrice.value = true
  try {
    const data = await previewCard(props.card.id, null, props.card.locale)
    marketPriceEur.value = data.pricing.cardmarket_eur
    averagePriceEur.value = data.pricing.average_price_eur
    if (data.image_url_high) {
      previewImageUrl.value = data.image_url_high
    }
  } catch {
    marketPriceEur.value = null
    averagePriceEur.value = null
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
    })
    ownedQuantity.value = res.card.quantity
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
    previewImageUrl.value = props.card.image
    void loadPreview()
  },
  { immediate: true },
)
</script>
