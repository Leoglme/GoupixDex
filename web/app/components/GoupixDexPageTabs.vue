<template>
  <div class="flex flex-wrap items-center gap-1 border-b border-(--app-line)" role="tablist">
    <NuxtLink
      v-for="item in props.items"
      :key="item.to"
      :to="item.to"
      class="relative flex items-center gap-1.5 rounded-t px-4 py-2.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-(--app-ink-soft) focus-visible:outline-none"
      :class="isActive(item) ? 'text-(--app-ink)' : 'text-(--app-ink-soft) hover:text-(--app-ink)'"
      :aria-current="isActive(item) ? 'page' : undefined"
    >
      <UIcon v-if="item.icon" :name="item.icon" class="h-4 w-4 shrink-0" />
      {{ item.label }}
      <span
        v-if="item.count !== undefined"
        class="ml-1 rounded-full bg-(--app-surface-2) px-2 py-0.5 font-mono text-xs"
      >
        {{ item.count }}
      </span>
      <span
        class="absolute inset-x-3 -bottom-px h-0.5 rounded-full transition-colors"
        :class="isActive(item) ? 'bg-(--app-accent)' : 'bg-transparent'"
      />
    </NuxtLink>
    <div v-if="$slots.trailing" class="ml-auto pb-1.5">
      <slot name="trailing" />
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { GoupixDexPageTabItem, GoupixDexPageTabsProps } from '~/types/GoupixDexPageTabs'

/**
 * Define the GoupixDexPageTabs props.
 */
const props: GoupixDexPageTabsProps = defineProps({
  items: {
    type: Array as PropType<GoupixDexPageTabItem[]>,
    required: true,
  },
})

const route = useRoute()

/**
 * Whether the given tab matches the current route.
 * @param item - The tab to test.
 * @returns True when the current path equals the tab target.
 */
function isActive(item: GoupixDexPageTabItem): boolean {
  return route.path === item.to
}
</script>
