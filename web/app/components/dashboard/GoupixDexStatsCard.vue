<template>
  <div
    class="app-card group transition-colors duration-200 hover:border-(--app-ink-soft)"
    :class="props.isCompactOnMobile ? 'p-3 sm:p-4' : 'p-4'"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="app-label truncate">{{ props.title }}</p>
        <p class="mt-1.5 text-xl font-semibold text-(--app-ink) tabular-nums sm:text-2xl">{{ props.value }}</p>
        <p
          v-if="typeof props.trendPercent === 'number'"
          class="mt-1 flex items-center gap-0.5 text-xs font-semibold tabular-nums"
          :class="{
            'text-(--app-green)': props.trendPercent > 0,
            'text-(--app-red)': props.trendPercent < 0,
            'text-muted': props.trendPercent === 0,
          }"
        >
          <UIcon v-if="props.trendPercent > 0" name="i-lucide-arrow-up" class="size-3" />
          <UIcon v-else-if="props.trendPercent < 0" name="i-lucide-arrow-down" class="size-3" />
          {{ props.trendPercent === 0 ? 'stable' : `${Math.abs(props.trendPercent)} %` }}
        </p>
        <p v-if="props.description" class="text-muted mt-1 text-xs">{{ props.description }}</p>
      </div>
      <div
        v-if="props.icon"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-(--app-accent-soft) transition-transform duration-200 group-hover:scale-105"
        :class="{ 'max-sm:hidden': props.isCompactOnMobile }"
      >
        <UIcon :name="props.icon" class="h-4 w-4 text-(--app-accent-ink)" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
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
  trendPercent: {
    type: Number as PropType<number | null>,
    default: null,
  },
  isCompactOnMobile: {
    type: Boolean,
    default: false,
  },
})
</script>
