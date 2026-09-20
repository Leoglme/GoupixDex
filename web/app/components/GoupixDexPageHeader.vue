<template>
  <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
    <div class="min-w-0">
      <p v-if="props.eyebrow" class="app-label flex items-center gap-1.5">
        <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
        {{ props.eyebrow }}
      </p>
      <h1 class="app-page-title" :class="props.eyebrow ? 'mt-2' : ''">{{ props.title }}</h1>
      <p v-if="props.description" class="mt-1.5 text-sm text-(--app-ink-soft)">{{ props.description }}</p>
    </div>
    <div
      v-if="$slots.actions"
      class="app-page-header-actions grid w-full grid-cols-1 gap-2 sm:flex sm:flex-row sm:flex-wrap sm:items-center sm:gap-3 lg:w-auto lg:justify-end [&>*]:min-w-0"
    >
      <slot name="actions" />
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { GoupixDexPageHeaderProps } from '~/types/GoupixDexPageHeader'

/**
 * Define the GoupixDexPageHeader props.
 */
const props: GoupixDexPageHeaderProps = defineProps({
  eyebrow: {
    type: String,
    default: undefined,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: undefined,
  },
})
</script>
