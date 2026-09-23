<template>
  <div class="space-y-6">
    <GoupixDexPageHeader
      title="Ma collection"
      description="Valeur, cartes possédées et classeurs — le suivi de ta collection Pokémon."
    >
      <template #actions>
        <UButton to="/collection" color="primary" variant="soft" icon="i-lucide-layers"> Ouvrir la collection </UButton>
      </template>
    </GoupixDexPageHeader>

    <div v-if="loading" class="flex justify-center py-16">
      <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
    </div>

    <template v-else-if="stats">
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <GoupixDexStatsCard
          title="Valeur estimée"
          :value="eur.format(stats.estimated_value_eur)"
          :description="`${numberFmt.format(stats.priced_cards)} carte(s) cotée(s)`"
          icon="i-lucide-coins"
        />
        <GoupixDexStatsCard
          title="Cartes uniques"
          :value="numberFmt.format(stats.unique_cards)"
          description="Cartes distinctes dans la collection"
          icon="i-lucide-layers"
        />
        <GoupixDexStatsCard
          title="Exemplaires"
          :value="numberFmt.format(stats.total_quantity)"
          description="Quantité totale possédée"
          icon="i-lucide-copy"
        />
        <GoupixDexStatsCard
          title="Sets représentés"
          :value="numberFmt.format(stats.unique_sets)"
          description="Extensions différentes"
          icon="i-lucide-book-open"
        />
      </div>

      <div class="grid gap-6 lg:grid-cols-2">
        <!-- Meilleurs investissements -->
        <UCard :ui="cardUi">
          <div class="mb-3 flex items-center justify-between gap-2">
            <h2 class="text-highlighted text-sm font-semibold">Meilleurs investissements</h2>
            <span
              v-if="stats.gain_percent != null"
              class="shrink-0 text-xs font-semibold tabular-nums"
              :class="gainTextClass(stats.gain_percent)"
            >
              {{ formatSignedPercent(stats.gain_percent) }}
            </span>
          </div>
          <div v-if="topGainers.length" class="divide-y divide-[var(--app-line-soft)]">
            <button
              v-for="card in topGainers"
              :key="card.id"
              type="button"
              class="group flex w-full cursor-pointer items-center gap-3 py-2.5 text-left first:pt-0 last:pb-0"
              @click="openCard(card.id)"
            >
              <span class="bg-muted/20 aspect-[63/88] w-10 shrink-0 overflow-hidden rounded">
                <GoupixDexCardImage
                  :image-url="card.image_url"
                  :tcgdex-card-id="card.tcgdex_card_id"
                  :alt="card.display_name"
                />
              </span>
              <span class="min-w-0 flex-1">
                <span class="text-highlighted block truncate text-sm font-medium group-hover:underline">
                  {{ card.display_name }}
                </span>
                <span class="text-muted block truncate text-xs tabular-nums">
                  {{ eur.format(card.purchase_price_eur ?? 0) }} → {{ eur.format(card.market_price_eur ?? 0) }}
                </span>
              </span>
              <span class="shrink-0 text-right">
                <span class="block text-sm font-semibold tabular-nums" :class="gainTextClass(card.gain_percent)">
                  {{ formatSignedPercent(card.gain_percent ?? 0) }}
                </span>
                <span v-if="card.gain_eur != null" class="text-muted block text-xs tabular-nums">
                  {{ card.gain_eur >= 0 ? '+' : '' }}{{ eur.format(card.gain_eur) }}
                </span>
              </span>
            </button>
          </div>
          <p v-else class="text-muted py-6 text-center text-sm">
            Renseigne un prix d'achat sur tes cartes pour suivre tes plus-values.
          </p>
        </UCard>

        <!-- Cartes les plus cotées -->
        <UCard :ui="cardUi">
          <div class="mb-3 flex items-center justify-between gap-2">
            <h2 class="text-highlighted text-sm font-semibold">Cartes les plus cotées</h2>
          </div>
          <div v-if="topCards.length" class="divide-y divide-[var(--app-line-soft)]">
            <button
              v-for="card in topCards"
              :key="card.id"
              type="button"
              class="group flex w-full cursor-pointer items-center gap-3 py-2.5 text-left first:pt-0 last:pb-0"
              @click="openCard(card.id)"
            >
              <span class="bg-muted/20 aspect-[63/88] w-10 shrink-0 overflow-hidden rounded">
                <GoupixDexCardImage
                  :image-url="card.image_url"
                  :tcgdex-card-id="card.tcgdex_card_id"
                  :alt="card.display_name"
                />
              </span>
              <span class="min-w-0 flex-1">
                <span class="text-highlighted block truncate text-sm font-medium group-hover:underline">
                  {{ card.display_name }}
                </span>
                <span class="text-muted block truncate text-xs">
                  {{ readableSetLabel(card.set_name, card.set_code, card.tcgdex_set_id) }}
                </span>
              </span>
              <span class="text-highlighted shrink-0 text-sm font-semibold tabular-nums">
                {{ eur.format(card.market_price_eur ?? 0) }}
              </span>
            </button>
          </div>
          <p v-else class="text-muted py-6 text-center text-sm">Aucune carte cotée pour l'instant.</p>
        </UCard>

        <!-- Classeurs -->
        <UCard :ui="cardUi">
          <div class="mb-3 flex items-center justify-between gap-2">
            <h2 class="text-highlighted flex items-center gap-1.5 text-sm font-semibold">
              Classeurs
              <span v-if="binders.length" class="text-muted font-normal tabular-nums">({{ binders.length }})</span>
            </h2>
            <NuxtLink
              to="/classeurs"
              class="text-muted hover:text-highlighted inline-flex shrink-0 items-center gap-1 text-xs font-medium transition-colors"
            >
              Tous <UIcon name="i-lucide-arrow-right" class="size-3" />
            </NuxtLink>
          </div>
          <div v-if="binders.length" class="divide-y divide-[var(--app-line-soft)]">
            <NuxtLink
              v-for="binder in binders"
              :key="binder.id"
              :to="`/classeurs/${binder.id}`"
              class="group block py-2.5 first:pt-0 last:pb-0"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-highlighted min-w-0 truncate text-sm font-medium group-hover:underline">
                  {{ binder.name }}
                </span>
                <span class="text-highlighted shrink-0 text-sm font-semibold tabular-nums">
                  {{ eur.format(binder.estimated_value_eur ?? 0) }}
                </span>
              </div>
              <div v-if="binder.pokedex_total" class="mt-1.5 flex items-center gap-2">
                <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-(--app-surface-2)">
                  <div class="h-full rounded-full bg-(--app-green)" :style="{ width: `${completionPct(binder)}%` }" />
                </div>
                <span class="text-muted shrink-0 text-[11px] tabular-nums">
                  {{ binder.pokedex_owned ?? 0 }} / {{ binder.pokedex_total }}
                </span>
              </div>
              <p v-else class="text-muted mt-0.5 text-xs tabular-nums">
                {{ binder.card_count }} carte{{ binder.card_count > 1 ? 's' : '' }}
              </p>
            </NuxtLink>
          </div>
          <p v-else class="text-muted py-6 text-center text-sm">Aucun classeur pour l'instant.</p>
        </UCard>

        <!-- Produits scellés -->
        <UCard :ui="cardUi">
          <div class="mb-3 flex items-center justify-between gap-2">
            <h2 class="text-highlighted flex items-center gap-1.5 text-sm font-semibold">
              Produits scellés
              <span v-if="sealedStats && sealedStats.unique_products > 0" class="text-muted font-normal tabular-nums">
                ({{ numberFmt.format(sealedStats.unique_products) }})
              </span>
            </h2>
            <span
              v-if="sealedStats && sealedStats.estimated_market_eur > 0"
              class="text-muted shrink-0 text-xs tabular-nums"
            >
              {{ eur.format(sealedStats.estimated_market_eur) }}
            </span>
          </div>
          <div v-if="topSealed.length" class="divide-y divide-[var(--app-line-soft)]">
            <button
              v-for="product in topSealed"
              :key="product.id"
              type="button"
              class="group flex w-full cursor-pointer items-center gap-3 py-2.5 text-left first:pt-0 last:pb-0"
              @click="openSealed(product.id)"
            >
              <span class="bg-muted/20 flex h-14 w-11 shrink-0 items-center justify-center overflow-hidden rounded-md">
                <img
                  v-if="product.image_url"
                  :src="product.image_url"
                  :alt="product.name"
                  class="h-full w-full object-contain"
                  referrerpolicy="no-referrer"
                  decoding="async"
                />
                <UIcon v-else :name="sealedProductTypeIcon(product.product_type)" class="text-muted size-6" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="text-highlighted block truncate text-sm font-medium group-hover:underline">
                  {{ product.name }}
                </span>
                <span class="text-muted block truncate text-xs">
                  {{ sealedProductTypeLabel(product.product_type) }}
                </span>
              </span>
              <span class="shrink-0 text-right">
                <span class="text-highlighted block text-sm font-semibold tabular-nums">
                  {{ product.market_price_eur != null ? eur.format(product.market_price_eur) : '—' }}
                </span>
                <span
                  v-if="product.gain_percent != null"
                  class="block text-xs font-medium tabular-nums"
                  :class="gainTextClass(product.gain_percent)"
                >
                  {{ formatSignedPercent(product.gain_percent) }}
                </span>
              </span>
            </button>
          </div>
          <p v-else class="text-muted py-6 text-center text-sm">
            Aucun produit scellé.
            <NuxtLink to="/collection/produits/add" class="text-primary underline underline-offset-2">
              En ajouter
            </NuxtLink>
          </p>
        </UCard>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { CollectionCard, CollectionStats } from '~/composables/useCollection'
import type { SealedProduct, SealedStats } from '~/composables/useSealed'
import type { BinderSummary } from '~/types/binders'
import { readableSetLabel } from '~/utils/cards/readableSet'
import { formatSignedPercent, sealedProductTypeIcon, sealedProductTypeLabel } from '~/utils/sealedProducts'

/**
 * Tableau de bord de la collection (onglet « Collection » du pilotage) : valeur, plus-values, classeurs, scellés.
 */
const { listCollection } = useCollection()
const { listBinders } = useBinders()
const { listSealed } = useSealed()
const drawerStack = useGoupixDrawerStack()
const toast = useToast()

const stats: Ref<CollectionStats | null> = ref<CollectionStats | null>(null)
const binders: Ref<BinderSummary[]> = ref<BinderSummary[]>([])
const topCards: Ref<CollectionCard[]> = ref<CollectionCard[]>([])
const topGainers: Ref<CollectionCard[]> = ref<CollectionCard[]>([])
const topSealed: Ref<SealedProduct[]> = ref<SealedProduct[]>([])
const sealedStats: Ref<SealedStats | null> = ref<SealedStats | null>(null)
const loading: Ref<boolean> = ref(true)

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})
const numberFmt: Intl.NumberFormat = new Intl.NumberFormat('fr-FR')

/** Padding resserré et uniforme des cartes de la collection (titre + liste dans le même corps). */
const cardUi: { body: string } = {
  body: 'p-4',
}

/**
 * Pourcentage de complétion d'un classeur Pokédex (possédées / total).
 * @param binder - Résumé du classeur.
 * @returns Pourcentage borné à [0, 100].
 */
function completionPct(binder: BinderSummary): number {
  const total = binder.pokedex_total ?? 0
  if (total <= 0) {
    return 0
  }
  return Math.min(100, Math.round(((binder.pokedex_owned ?? 0) / total) * 100))
}

/**
 * Couleur d'un pourcentage de plus-value (vert si positif ou nul, rouge si perte).
 * @param percent - Pourcentage de plus-value (peut être null).
 * @returns Classe de couleur applicable.
 */
function gainTextClass(percent: number | null): string {
  return (percent ?? 0) >= 0 ? 'text-(--app-green)' : 'text-(--app-red)'
}

/**
 * Ouvre la fiche d'une carte dans le drawer partagé.
 * @param cardId - Identifiant de la carte de collection.
 * @returns {void}
 */
function openCard(cardId: number): void {
  drawerStack.pushCard(cardId)
}

/**
 * Ouvre la fiche d'un produit scellé dans le drawer partagé.
 * @param sealedId - Identifiant du produit scellé.
 * @returns {void}
 */
function openSealed(sealedId: number): void {
  drawerStack.pushSealed(sealedId)
}

/**
 * Charge les stats de collection, les classeurs, les plus-values et les produits scellés.
 * @returns Résolue après chargement.
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const [collection, binderList, sealed] = await Promise.all([listCollection(), listBinders(), listSealed()])
    stats.value = collection.stats
    topCards.value = [...collection.items]
      .filter((card) => card.market_price_eur != null)
      .sort((a, b) => (b.market_price_eur ?? 0) - (a.market_price_eur ?? 0))
      .slice(0, 5)
    topGainers.value = [...collection.items]
      .filter((card) => card.gain_percent != null)
      .sort((a, b) => (b.gain_percent ?? 0) - (a.gain_percent ?? 0))
      .slice(0, 5)
    binders.value = [...binderList].sort((a, b) => (b.estimated_value_eur ?? 0) - (a.estimated_value_eur ?? 0))
    sealedStats.value = sealed.stats
    topSealed.value = [...sealed.items]
      .sort((a, b) => (b.market_price_eur ?? 0) - (a.market_price_eur ?? 0))
      .slice(0, 6)
  } catch {
    toast.add({ title: 'Impossible de charger la collection', color: 'error' })
  } finally {
    loading.value = false
  }
}

watch(
  () => [drawerStack.cardMutationCounter.value, drawerStack.sealedMutationCounter.value],
  () => {
    void load()
  },
)

onMounted((): void => {
  void load()
})
</script>
