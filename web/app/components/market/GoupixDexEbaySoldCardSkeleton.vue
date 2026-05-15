<template>
  <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
    <article
      v-for="i in count"
      :key="i"
      class="border-default bg-elevated/30 relative flex flex-col overflow-hidden rounded-xl border"
    >
      <div class="bg-muted/40 aspect-square animate-pulse" />
      <div class="space-y-3 p-3">
        <div class="space-y-1.5">
          <div class="bg-muted/40 h-3 w-full animate-pulse rounded" />
          <div class="bg-muted/40 h-3 w-5/6 animate-pulse rounded" />
        </div>
        <div class="bg-muted/40 h-5 w-20 animate-pulse rounded" />
        <div class="bg-muted/30 h-2.5 w-24 animate-pulse rounded" />
        <div class="bg-muted/30 mt-2 h-7 w-28 animate-pulse rounded" />
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ count?: number }>(), { count: 8 })
</script>
