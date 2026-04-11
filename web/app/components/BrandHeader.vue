<script setup lang="ts">
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

defineProps<{
  collapsed?: boolean
}>()
</script>

<template>
  <NuxtLink
    to="/dashboard"
    class="flex items-center rounded-lg hover:bg-elevated/80 transition-colors shrink-0"
    :class="collapsed ? 'justify-center px-1 py-2.5 w-full min-w-9' : 'min-w-0 gap-2 px-2 py-2'"
  >
    <span
      class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-elevated/40 ring-1 ring-default/40"
    >
      <img
        :src="logoUrl"
        alt="GoupixDex"
        class="size-8 max-h-8 max-w-8 object-contain"
        width="32"
        height="32"
      >
    </span>
    <span
      v-if="!collapsed"
      class="min-w-0 font-semibold text-highlighted truncate"
    >GoupixDex</span>
  </NuxtLink>
</template>
