<template>
  <div
    class="inline-flex flex-wrap items-center gap-1 border-b border-(--app-line)"
    role="tablist"
    aria-label="Mode d'affichage"
  >
    <button
      v-for="item in items"
      :key="item.value"
      type="button"
      role="tab"
      :aria-selected="model === item.value"
      class="relative inline-flex cursor-pointer items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-(--app-accent) focus-visible:outline-none"
      :class="model === item.value ? 'text-primary' : 'text-muted hover:text-(--app-ink)'"
      @click="model = item.value"
    >
      <UIcon v-if="item.icon" :name="item.icon" class="size-4 shrink-0" aria-hidden />
      {{ item.label }}
      <span
        class="absolute inset-x-2 -bottom-px h-0.5 rounded-full transition-colors"
        :class="model === item.value ? 'bg-primary' : 'bg-transparent'"
        aria-hidden
      />
    </button>
  </div>
</template>

<script setup lang="ts">
export type GoupixDexCollectionViewTabItem = {
  label: string
  value: string
  icon?: string
}

const model = defineModel<string>({ required: true })

defineProps<{
  items: GoupixDexCollectionViewTabItem[]
}>()
</script>
