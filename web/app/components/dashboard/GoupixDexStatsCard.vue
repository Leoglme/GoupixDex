<template>
  <div class="app-card group p-4 transition-colors duration-200 hover:border-(--app-ink-soft)">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="app-label truncate">{{ props.title }}</p>
        <p class="mt-1.5 text-xl font-semibold text-(--app-ink) tabular-nums sm:text-2xl">{{ props.value }}</p>
        <p v-if="props.description" class="text-muted mt-1 text-xs">{{ props.description }}</p>
      </div>
      <div
        v-if="props.icon"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-(--app-accent-soft) transition-transform duration-200 group-hover:scale-105"
      >
        <UIcon :name="props.icon" class="h-4 w-4 text-(--app-accent-ink)" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { GoupixDexStatsCardProps } from '~/types/GoupixDexStatsCard'

/**
 * Define the GoupixDexStatsCard props.
 */
const props: GoupixDexStatsCardProps = defineProps({
  title: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number],
    required: true,
  },
  icon: {
    type: String,
    default: undefined,
  },
  description: {
    type: String,
    default: undefined,
  },
})
</script>
