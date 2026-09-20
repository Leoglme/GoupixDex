<template>
  <p v-if="cards.length === 0" class="text-xs text-(--app-faint)">Range d'abord des cartes dans le classeur.</p>
  <div v-else class="grid max-h-52 grid-cols-5 gap-2 overflow-y-auto pr-1">
    <button
      v-for="c in cards"
      :key="c.id"
      type="button"
      :title="c.name"
      :aria-pressed="isSelected(c.id)"
      class="group/cover relative"
      @click="$emit('pick', c.id)"
    >
      <div
        class="card-tile aspect-[63/88] transition"
        :class="
          isSelected(c.id)
            ? 'outline-2 outline-offset-2 outline-(--app-accent)'
            : 'opacity-80 group-hover/cover:opacity-100'
        "
      >
        <GoupixDexBinderCardImage :src="c.image_url" :alt="c.name" />
      </div>
      <span
        v-if="order?.(c.id) != null"
        class="tile-badge num absolute -top-1.5 -right-1.5 z-10 flex h-5 w-5 items-center justify-center !rounded-full !px-0"
      >
        {{ (order!(c.id) ?? 0) + 1 }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
export type EditorCard = { id: string; name: string; image_url: string }

defineProps<{
  cards: EditorCard[]
  isSelected: (id: string) => boolean
  order?: (id: string) => number | null
}>()

defineEmits<{ pick: [string] }>()
</script>
