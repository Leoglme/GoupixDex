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

    <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-8">
      <div
        v-for="c in visibleCards"
        :key="c.id"
        role="button"
        tabindex="0"
        class="group bg-elevated/30 border-default focus-visible:ring-primary relative cursor-pointer overflow-hidden rounded-xl border text-left transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
        @click="emit('preview', c)"
        @keydown.enter.prevent="emit('preview', c)"
      >
        <div class="bg-muted/30 relative aspect-[63/88] w-full">
          <GoupixDexCardImage
            :image-url="c.thumbUrl"
            :tcgdex-card-id="c.id"
            :alt="c.displayName"
            img-class="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.03]"
          />
          <div v-if="pendingCardId === c.id" class="absolute inset-0 flex items-center justify-center bg-black/40">
            <UIcon name="i-lucide-loader-2" class="size-7 animate-spin text-white" />
          </div>
          <span
            v-if="ownedQty(c.id) > 0"
            class="bg-success/90 text-inverted absolute top-1.5 left-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums backdrop-blur-sm"
          >
            ×{{ ownedQty(c.id) }}
          </span>
          <button
            type="button"
            class="bg-elevated/95 text-highlighted focus-visible:ring-primary absolute right-1.5 bottom-1.5 flex size-7 items-center justify-center rounded-full backdrop-blur-sm transition-colors hover:bg-(--app-accent) hover:text-white focus-visible:ring-2 focus-visible:outline-none"
            :disabled="pendingCardId === c.id"
            :aria-label="`Ajouter ${c.displayName} directement`"
            @click.stop="emit('add', c)"
          >
            <UIcon
              :name="pendingCardId === c.id ? 'i-lucide-loader-2' : 'i-lucide-plus'"
              class="size-4"
              :class="pendingCardId === c.id ? 'animate-spin' : ''"
            />
          </button>
        </div>
        <div class="space-y-0.5 px-2 py-1.5">
          <p class="text-highlighted truncate text-xs font-medium">{{ c.displayName }}</p>
          <p class="text-muted text-[10px]">#{{ c.localId }}</p>
        </div>
      </div>
    </div>

    <p v-if="!visibleCards.length" class="text-muted py-8 text-center text-sm">Aucune carte pour ce filtre.</p>
  </div>
</template>

<script setup lang="ts">
export type CatalogSetCardRow = {
  id: string
  localId: string
  displayName: string
  thumbUrl?: string
}

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
