<template>
  <div v-if="lastAddFromSheet" class="mt-2 flex items-center gap-3 pl-3 text-sm">
    <span class="flex size-9 shrink-0 items-center justify-center">
      <UIcon name="i-lucide-circle-check" class="size-4 text-emerald-300" />
    </span>
    <span class="min-w-0 flex-1 truncate text-white/80">{{ lastAddFromSheetLabel }}</span>
    <button
      type="button"
      class="flex h-11 shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-3 font-semibold text-white/80 transition-colors hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="props.isDisabled"
      @click="emit('undo')"
    >
      <UIcon
        :name="props.isUndoingLastAdd ? 'i-lucide-loader-circle' : 'i-lucide-undo-2'"
        class="size-4"
        :class="{ 'animate-spin': props.isUndoingLastAdd }"
      />
      Annuler
    </button>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type { GoupixDexScannedCardUndoAddProps } from '~/types/GoupixDexScannedCardUndoAdd'
import type { ScannedCardAdd } from '~/types/ScannedCardSheet'

const props: GoupixDexScannedCardUndoAddProps = defineProps({
  addsFromSheet: {
    type: Array as PropType<ScannedCardAdd[]>,
    required: true,
  },
  isUndoingLastAdd: {
    type: Boolean,
    default: false,
  },
  isDisabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  undo: []
}>()

const lastAddFromSheet: ComputedRef<ScannedCardAdd | null> = computed(
  (): ScannedCardAdd | null => props.addsFromSheet.at(-1) ?? null,
)

const lastAddFromSheetLabel: ComputedRef<string> = computed((): string => {
  const binderName: string | null = lastAddFromSheet.value?.binderName ?? null
  return binderName ? `Rangée dans ${binderName}` : 'Ajoutée à ma collection'
})
</script>
