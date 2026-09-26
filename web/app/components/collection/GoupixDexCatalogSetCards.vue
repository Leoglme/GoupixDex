<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center gap-2">
      <UButton
        v-for="opt in ownFilterOptions"
        :key="opt.value"
        size="sm"
        :color="ownFilter === opt.value ? 'primary' : 'neutral'"
        :variant="ownFilter === opt.value ? 'solid' : 'subtle'"
        @click="ownFilter = opt.value"
      >
        {{ opt.label }}
      </UButton>
      <span class="text-muted ml-auto text-sm tabular-nums">
        {{ ownedDistinct }}/{{ cards.length }} possédées · {{ completionPct }} %
      </span>
    </div>

    <p v-if="scansMissing" class="border-default text-muted rounded-xl border px-4 py-3 text-sm">
      TCGdex n'a pas encore les scans de cette extension — les cartes restent ajoutables par nom et numéro.
    </p>

    <div class="app-pokemon-card-grid">
      <GoupixDexPokemonCardTile
        v-for="c in visibleCards"
        :key="c.id"
        :name="c.displayName"
        :image-url="c.thumbUrl ?? null"
        :tcgdex-card-id="c.id"
        :set-number-label="`#${c.numberLabel}`"
        :owned-quantity="ownedQty(c.id)"
        is-addable
        :is-adding="pendingCardId === c.id"
        @select="emit('preview', c)"
        @add="emit('add', c)"
      />
    </div>

    <p v-if="!visibleCards.length" class="text-muted py-8 text-center text-sm">Aucune carte pour ce filtre.</p>
  </div>
</template>

<script setup lang="ts">
import type { CatalogSetCardRow } from '~/types/GoupixDexCatalogSetCards'

const props = defineProps<{
  cards: CatalogSetCardRow[]
  ownedByCardId: Map<string, number>
  pendingCardId: string | null
  scansMissing?: boolean
}>()

const emit = defineEmits<{
  preview: [CatalogSetCardRow]
  add: [CatalogSetCardRow]
}>()

const ownFilter = ref<'all' | 'owned' | 'missing'>('all')

const ownFilterOptions = [
  { label: 'Toutes', value: 'all' as const },
  { label: 'Dans ma collection', value: 'owned' as const },
  { label: 'Manquantes', value: 'missing' as const },
]

function ownedQty(cardId: string): number {
  return props.ownedByCardId.get(cardId) ?? 0
}

const ownedDistinct = computed(() => props.cards.filter((c) => ownedQty(c.id) > 0).length)

const completionPct = computed(() => {
  if (!props.cards.length) {
    return 0
  }
  return Math.round((100 * ownedDistinct.value) / props.cards.length)
})

const visibleCards = computed(() => {
  if (ownFilter.value === 'owned') {
    return props.cards.filter((c) => ownedQty(c.id) > 0)
  }
  if (ownFilter.value === 'missing') {
    return props.cards.filter((c) => ownedQty(c.id) === 0)
  }
  return props.cards
})
</script>
