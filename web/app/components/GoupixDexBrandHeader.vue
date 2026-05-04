<template>
  <NuxtLink
    to="/dashboard"
    class="hover:bg-elevated/80 flex shrink-0 items-center rounded-lg transition-colors"
    :class="isCollapsed ? 'w-full min-w-9 justify-center px-1 py-2.5' : 'min-w-0 gap-2 px-2 py-2'"
  >
    <span
      class="bg-elevated/40 ring-default/40 flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1"
    >
      <img :src="logoUrl" alt="GoupixDex" class="size-8 max-h-8 max-w-8 object-contain" width="32" height="32" />
    </span>
    <span v-if="!isCollapsed" class="text-highlighted min-w-0 truncate font-semibold">GoupixDex</span>
  </NuxtLink>
</template>

<script setup lang="ts">
import type { ComputedRef } from 'vue'
import type { GoupixDexBrandHeaderProps } from '~/types/GoupixDexBrandHeader'

import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

/**
 * Define the GoupixDexBrandHeader props.
 */
const props: GoupixDexBrandHeaderProps = defineProps({
  collapsed: {
    type: Boolean,
    default: false,
  },
})

const isCollapsed: ComputedRef<boolean> = computed((): boolean => Boolean(props.collapsed))
</script>
