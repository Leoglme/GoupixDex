<template>
  <div class="app-page-tabs-scroll border-b border-(--app-line)">
    <div
      class="flex min-w-max flex-nowrap items-stretch gap-1 sm:min-w-0 sm:flex-wrap"
      :class="tabRowMobileClass"
      role="tablist"
    >
      <NuxtLink
        v-for="item in props.items"
        :key="item.to"
        :to="item.to"
        class="relative flex min-h-11 items-center justify-center gap-1.5 rounded-t px-4 py-2.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-(--app-ink-soft) focus-visible:outline-none max-md:min-w-0 max-md:flex-1 max-md:px-2"
        :class="isActive(item) ? 'text-(--app-ink)' : 'text-(--app-ink-soft) hover:text-(--app-ink)'"
        :aria-current="isActive(item) ? 'page' : undefined"
      >
        <UIcon v-if="item.icon" :name="item.icon" class="h-4 w-4 shrink-0" />
        <span class="truncate">{{ item.label }}</span>
        <span
          v-if="item.count !== undefined"
          class="ml-0.5 rounded-full bg-(--app-surface-2) px-2 py-0.5 font-mono text-xs"
        >
          {{ item.count }}
        </span>
        <span
          class="absolute inset-x-2 -bottom-px h-0.5 rounded-full transition-colors sm:inset-x-3"
          :class="isActive(item) ? 'bg-(--app-accent)' : 'bg-transparent'"
        />
      </NuxtLink>
      <div v-if="$slots.trailing" class="ml-auto shrink-0 pb-1.5 max-md:hidden sm:ml-auto">
        <slot name="trailing" />
      </div>
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

const tabRowMobileClass = computed(() => {
  if (props.items.length === 2) {
    return 'max-md:grid max-md:w-full max-md:min-w-0 max-md:grid-cols-2 max-md:gap-0'
  }
  if (props.items.length >= 2 && props.items.length <= 5) {
    return 'max-md:w-full max-md:min-w-0'
  }
  return ''
})

/**
 * Whether the given tab matches the current route.
 * @param item - The tab to test.
 * @returns True when the current path equals the tab target.
 */
function isActive(item: GoupixDexPageTabItem): boolean {
  return route.path === item.to
}
</script>
