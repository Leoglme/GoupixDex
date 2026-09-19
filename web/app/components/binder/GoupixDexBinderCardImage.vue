<template>
  <img v-if="src" :src="src" :alt="alt" class="h-full w-full object-cover" loading="lazy" decoding="async" />
  <div v-else class="flex h-full w-full items-center justify-center bg-(--app-surface-2) text-xs text-(--app-faint)">
    —
  </div>
</template>

<script setup lang="ts">
defineProps<{
  src: string | null | undefined
  alt?: string
}>()
</script>
