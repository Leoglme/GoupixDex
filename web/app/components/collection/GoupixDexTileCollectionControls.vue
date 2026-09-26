<template>
  <span
    v-if="props.ownedQuantity > 0"
    class="absolute top-1.5 left-1.5 flex items-center gap-0.5 rounded-full bg-(--app-green) px-1.5 py-0.5 text-[11px] font-bold text-white tabular-nums shadow-sm"
  >
    <UIcon name="i-lucide-check" class="size-3" />{{ props.ownedQuantity }}
  </span>
  <button
    v-if="props.isAddable"
    type="button"
    class="bg-elevated/95 text-highlighted focus-visible:ring-primary absolute right-1.5 bottom-1.5 flex size-7 items-center justify-center rounded-full shadow-sm backdrop-blur-sm transition-colors hover:bg-(--app-accent) hover:text-white focus-visible:ring-2 focus-visible:outline-none"
    :disabled="props.isAdding"
    :aria-label="`Ajouter ${props.itemName} directement`"
    @click.stop="emit('add')"
    @keydown.enter.stop
  >
    <UIcon
      :name="props.isAdding ? 'i-lucide-loader-2' : 'i-lucide-plus'"
      class="size-4"
      :class="props.isAdding ? 'animate-spin' : ''"
    />
  </button>
</template>

<script lang="ts" setup>
import type { GoupixDexTileCollectionControlsProps } from '~/types/GoupixDexTileCollectionControls'

const props: GoupixDexTileCollectionControlsProps = defineProps({
  itemName: {
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
  (e: 'add'): void
}>()
</script>
