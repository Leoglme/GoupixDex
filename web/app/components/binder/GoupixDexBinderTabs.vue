<template>
  <div
    aria-label="Onglets"
    :class="
      orientation === 'vertical'
        ? 'scrollbar-none absolute top-6 right-1 z-30 flex max-h-[min(70vh,32rem)] flex-col gap-1.5 overflow-y-auto pb-1'
        : 'scrollbar-none mt-4 flex justify-center gap-1.5 overflow-x-auto pb-1'
    "
  >
    <button
      type="button"
      :aria-current="!opened ? 'page' : undefined"
      class="inline-flex shrink-0 items-center justify-center shadow-md transition"
      :class="tabClass(!opened)"
      @click="$emit('close')"
    >
      <UIcon name="i-lucide-book" class="h-3.5 w-3.5" />
    </button>
    <button
      v-for="v in totalViews"
      :key="v - 1"
      type="button"
      :data-tab="v - 1"
      :aria-current="opened && view === v - 1 ? 'page' : undefined"
      :class="[
        tabClass(opened && view === v - 1),
        dragging && overTab === `tab:${v - 1}` ? 'ring-2 ring-(--app-accent)' : '',
      ]"
      @click="$emit('open-to', v - 1)"
    >
      {{ labelOf(v - 1) }}
    </button>
    <button
      v-if="!readOnly"
      type="button"
      :class="tabClass(false, true)"
      aria-label="Ajouter une feuille"
      @click="$emit('add-sheet')"
    >
      <UIcon name="i-lucide-plus" class="h-3.5 w-3.5" />
    </button>
    <button
      v-if="canRemoveSheet"
      type="button"
      :class="tabClass(false, true)"
      aria-label="Retirer la dernière feuille"
      @click="$emit('remove-sheet')"
    >
      <UIcon name="i-lucide-minus" class="h-3.5 w-3.5" />
    </button>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  orientation: 'vertical' | 'horizontal'
  opened: boolean
  view: number
  totalViews: number
  labelOf: (v: number) => string
  readOnly: boolean
  canRemoveSheet: boolean
  dragging: boolean
  overTab: string | null
}>()

defineEmits<{ close: []; 'open-to': [number]; 'add-sheet': []; 'remove-sheet': [] }>()

function tabClass(active: boolean, dashed = false) {
  const base =
    props.orientation === 'vertical'
      ? 'h-10 min-w-[2.85rem] rounded-r-lg border border-l-0 px-2 text-[11px] font-semibold tabular-nums'
      : 'h-9 min-w-[2.75rem] rounded-lg border px-2.5 text-[11px] font-semibold tabular-nums'
  if (active) return `${base} border-(--app-accent) bg-(--app-accent) text-white`
  if (dashed)
    return `${base} border-dashed border-(--app-line) bg-(--app-surface-2)/60 text-(--app-ink-soft) hover:text-(--app-ink)`
  return `${base} border-(--app-line) bg-(--app-surface-2) text-(--app-ink-soft) hover:text-(--app-ink)`
}
</script>
