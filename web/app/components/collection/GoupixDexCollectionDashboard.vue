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
        <!-- Classeurs -->
        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <p class="text-highlighted text-sm font-medium">Classeurs</p>
              <NuxtLink to="/classeurs" class="text-primary text-xs underline underline-offset-2"> Tous </NuxtLink>
            </div>
          </template>
          <ul v-if="binders.length" class="space-y-2.5">
            <li v-for="binder in binders" :key="binder.id">
              <NuxtLink
                :to="`/classeurs/${binder.id}`"
                class="hover:bg-elevated/50 block rounded-lg px-2.5 py-2 transition-colors"
              >
                <div class="flex items-center justify-between gap-3">
                  <span class="text-highlighted min-w-0 truncate text-sm font-medium">{{ binder.name }}</span>
                  <span class="text-highlighted shrink-0 text-sm font-semibold tabular-nums">
                    {{ eur.format(binder.estimated_value_eur ?? 0) }}
                  </span>
                </div>
                <div v-if="binder.pokedex_total" class="mt-2 flex items-center gap-2">
                  <div class="bg-elevated h-1.5 flex-1 overflow-hidden rounded-full">
                    <div class="h-full rounded-full bg-(--app-green)" :style="{ width: `${completionPct(binder)}%` }" />
                  </div>
                  <span class="text-muted shrink-0 text-[11px] tabular-nums">
                    {{ binder.pokedex_owned ?? 0 }} / {{ binder.pokedex_total }}
                  </span>
                </div>
                <p v-else class="text-muted mt-1 text-xs tabular-nums">
                  {{ binder.card_count }} carte{{ binder.card_count > 1 ? 's' : '' }}
                </p>
              </NuxtLink>
            </li>
          </ul>
          <p v-else class="text-muted py-8 text-center text-sm">Aucun classeur pour l'instant.</p>
        </UCard>

        <!-- Cartes les plus cotées -->
        <UCard>
          <template #header>
            <p class="text-highlighted text-sm font-medium">Cartes les plus cotées</p>
          </template>
          <ul v-if="topCards.length" class="space-y-2.5">
            <li v-for="card in topCards" :key="card.id">
              <button
                type="button"
                class="hover:bg-elevated/50 flex w-full items-center gap-3 rounded-lg px-2.5 py-1.5 text-left transition-colors"
                @click="openCard(card.id)"
              >
                <span class="bg-muted/20 aspect-[63/88] w-8 shrink-0 overflow-hidden rounded">
                  <GoupixDexCardImage
                    :image-url="card.image_url"
                    :tcgdex-card-id="card.tcgdex_card_id"
                    :alt="card.display_name"
                  />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="text-highlighted block truncate text-sm font-medium">{{ card.display_name }}</span>
                  <span class="text-muted block truncate text-xs">
                    {{ readableSetLabel(card.set_name, card.set_code, card.tcgdex_set_id) }}
                  </span>
                </span>
                <span class="text-highlighted shrink-0 text-sm font-semibold tabular-nums">
                  {{ eur.format(card.market_price_eur ?? 0) }}
                </span>
              </button>
            </li>
          </ul>
          <p v-else class="text-muted py-8 text-center text-sm">Aucune carte cotée pour l'instant.</p>
        </UCard>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { CollectionCard, CollectionStats } from '~/composables/useCollection'
import type { BinderSummary } from '~/types/binders'
import { readableSetLabel } from '~/utils/cards/readableSet'

/**
 * Tableau de bord de la collection (onglet « Collection » du pilotage) : valeur, cartes, classeurs.
 */
const { listCollection } = useCollection()
const { listBinders } = useBinders()
const drawerStack = useGoupixDrawerStack()
const toast = useToast()

const stats: Ref<CollectionStats | null> = ref<CollectionStats | null>(null)
const binders: Ref<BinderSummary[]> = ref<BinderSummary[]>([])
const topCards: Ref<CollectionCard[]> = ref<CollectionCard[]>([])
const loading: Ref<boolean> = ref(true)

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})
const numberFmt: Intl.NumberFormat = new Intl.NumberFormat('fr-FR')

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
 * Ouvre la fiche d'une carte dans le drawer partagé.
 * @param cardId - Identifiant de la carte de collection.
 * @returns {void}
 */
function openCard(cardId: number): void {
  drawerStack.pushCard(cardId)
}

/**
 * Charge les stats de collection, les classeurs et les cartes les plus cotées.
 * @returns Résolue après chargement.
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const [collection, binderList] = await Promise.all([listCollection(), listBinders()])
    stats.value = collection.stats
    topCards.value = [...collection.items]
      .filter((card) => card.market_price_eur != null)
      .sort((a, b) => (b.market_price_eur ?? 0) - (a.market_price_eur ?? 0))
      .slice(0, 5)
    binders.value = [...binderList].sort((a, b) => (b.estimated_value_eur ?? 0) - (a.estimated_value_eur ?? 0))
  } catch {
    toast.add({ title: 'Impossible de charger la collection', color: 'error' })
  } finally {
    loading.value = false
  }
}

watch(
  () => drawerStack.cardMutationCounter.value,
  () => {
    void load()
  },
)

onMounted((): void => {
  void load()
})
</script>
