<template>
  <div
    role="button"
    tabindex="0"
    class="group bg-elevated/30 focus-visible:ring-primary flex h-full cursor-pointer flex-col overflow-hidden rounded-xl border text-left transition-all hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
    :class="
      props.ownedQuantity > 0
        ? 'border-(--app-green) ring-2 ring-(--app-green)'
        : 'border-default hover:border-(--app-accent)'
    "
    @click="emit('select')"
    @keydown.enter.prevent="emit('select')"
  >
    <div class="bg-muted/20 relative aspect-[63/88] w-full overflow-hidden">
      <GoupixDexCardImage
        :image-url="props.imageUrl"
        :tcgdex-card-id="props.tcgdexCardId"
        :alt="props.name"
        img-class="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.03]"
      />
      <div v-if="props.isAdding" class="absolute inset-0 flex items-center justify-center bg-black/40">
        <UIcon name="i-lucide-loader-2" class="size-7 animate-spin text-white" />
      </div>
      <slot name="badges" />
      <GoupixDexTileCollectionControls
        :item-name="props.name"
        :owned-quantity="props.ownedQuantity"
        :is-addable="props.isAddable"
        :is-adding="props.isAdding"
        @add="emit('add')"
      />
    </div>
    <div class="min-w-0 space-y-0.5 p-2.5">
      <p class="text-highlighted truncate text-sm leading-snug font-medium">{{ props.name }}</p>
      <p class="text-muted truncate text-xs tabular-nums">{{ props.setNumberLabel }}</p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { GoupixDexPokemonCardTileProps } from '~/types/GoupixDexPokemonCardTile'

const props: GoupixDexPokemonCardTileProps = defineProps({
  name: {
    type: String,
    required: true,
  },
  imageUrl: {
    type: String as PropType<string | null>,
    default: null,
  },
  tcgdexCardId: {
    type: String as PropType<string | null>,
    default: null,
  },
  setNumberLabel: {
    type: String,
    required: true,
  },
  ownedQuantity: {
    type: Number,
    default: 0,
  },
  isAddable: {
    type: Boolean,
    default: false,
  },
  isAdding: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  select: []
  add: []
}>()
</script>
