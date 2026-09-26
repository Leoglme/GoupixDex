<template>
  <NuxtLink
    :to="props.to"
    class="border-default bg-elevated/30 group focus-visible:ring-primary flex h-full flex-col items-center gap-3 rounded-xl border p-4 text-center transition-all hover:-translate-y-0.5 hover:border-(--app-accent) hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
  >
    <div class="flex h-14 w-full items-center justify-center">
      <slot name="logo" />
    </div>
    <div class="mt-auto w-full min-w-0">
      <p class="text-highlighted truncate text-sm leading-tight font-medium">{{ props.name }}</p>
      <p class="text-muted mt-1 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs tabular-nums">
        <span v-if="props.setCode" class="bg-muted/30 rounded px-1.5 py-0.5 font-mono uppercase">{{
          props.setCode
        }}</span>
        <span v-if="props.summaryLabel">{{ props.summaryLabel }}</span>
      </p>
    </div>
  </NuxtLink>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { GoupixDexExtensionTileProps } from '~/types/GoupixDexExtensionTile'

const props: GoupixDexExtensionTileProps = defineProps({
  to: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  setCode: {
    type: String as PropType<string | null>,
    default: null,
  },
  summaryLabel: {
    type: String as PropType<string | null>,
    default: null,
  },
})
</script>
